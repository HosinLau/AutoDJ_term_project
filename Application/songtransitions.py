# Copyright 2017 Len Vande Veire, IDLab, Department of Electronics and Information Systems, Ghent University
# This file is part of the source code for the Auto-DJ research project, published in Vande Veire, Len, and De Bie, Tijl, "From raw audio to a seamless mix: an artificial intelligence approach to creating an automated DJ system.", 2018 (submitted)
# Released under AGPLv3 license.

import numpy as np
import itertools
import yodel.filter	# For low pass and high pass bench filters
import scipy.signal
import tracklister
import random
import librosa.effects
import math
import time

import logging
logger = logging.getLogger('colorlogger')
logging.basicConfig(filename="/home/hosin/log.txt")

doppler_prob = 0.15
doppler_span = 1
doppler_stages = 16

high_pass_echo_prob = 0.15
low_pass_echo_prob = 0.15
echoes = 7
echo_delay = 0.5
echo_decay = 0.8
echo_span = 0.5

low_pass_enter_prob = 0.15
low_pass_enter_span = 9

high_pass_drag_prob = 0.15
drag_delay = 0.05

def high_pass_drag(master_audio_clip, length):
    high_pass_filter = yodel.filter.Biquad()
    original = master_audio_clip.tolist()
    audio = list(original)
    for i in range(16):
        high_pass_filter.high_pass(44100, min(3000, 500 + i * 300), 1.0 / np.sqrt(2))
        start = len(master_audio_clip) * i/16
        end = len(master_audio_clip) * (i+1)/16
        drag = [a * 0.5 for a in scipy.signal.lfilter(high_pass_filter._b_coeffs, high_pass_filter._a_coeffs, original[start:end])]
        start = max(0, int(start + drag_delay * 44100))
        end =  min(length, int(end + drag_delay * 44100))
        for t in range(start, end):
            audio[t] += drag[t-start]
    return np.array(audio)

def low_pass_enter(slave_audio_clip, length):
    low_pass_filter = yodel.filter.Biquad()
    low_pass_filter.low_pass(44100, 2000, 1.0 / np.sqrt(2))
    original = slave_audio_clip.tolist()
    audio = [0 for t in range(length)]
    audio[:low_pass_enter_span] = [a * 2 for a in scipy.signal.lfilter(low_pass_filter._b_coeffs, low_pass_filter._a_coeffs, original[:low_pass_enter_span])]
    for i in range(10):
        low_pass_filter.low_pass(44100, 2000 + i * 500, 1.0 / np.sqrt(2))
        start = (length-low_pass_enter_span)*i/10
        end = low_pass_enter_span+(length-low_pass_enter_span)*(i+1)/10
        audio[start:end] = [a * (2 - i * 0.1) for a in scipy.signal.lfilter(low_pass_filter._b_coeffs, low_pass_filter._a_coeffs, original[start:end])]
    return np.array(audio)

def high_pass_echo_effect(master_audio_clip, length):
    try:
        high_pass_filter = yodel.filter.Biquad()
        original = master_audio_clip.tolist()
        audio = []
        for i in range(echoes + 1):
            high_pass_filter.high_pass(44100, 100 + 1000 * i/echoes, 1.0 / np.sqrt(2))
            syllable = scipy.signal.lfilter(high_pass_filter._b_coeffs, high_pass_filter._a_coeffs, original)
            echo = [0 for t in range(int(len(syllable) * echo_delay * i))]
            echo.extend([a * math.pow(echo_decay, i) for a in syllable])
            audio.extend([0 for t in range(len(echo)-len(audio))])
            audio = [audio[t] + echo[t] for t in range(len(audio))]
    except Exception as e:
        logger.debug(e)
    audio.extend([0 for t in range(length - len(audio))])
    logger.debug('length = ' + str(length))
    logger.debug('original len = ' + str(len(original)))
    audio = [audio[t] * ((t/length)*(t/length)*(-3.43)+(t/length)*3.37+0.7) for t in range(length)]
    return np.array(audio[:length])

def low_pass_echo_effect(master_audio_clip, length):
    try:
        low_pass_filter = yodel.filter.Biquad()
        original = master_audio_clip.tolist()
        audio = []
        for i in range(echoes + 1):
            low_pass_filter.low_pass(44100, 2000 + 3000 * ((echoes-i)/echoes), 1.0 / np.sqrt(2))
            syllable = scipy.signal.lfilter(low_pass_filter._b_coeffs, low_pass_filter._a_coeffs, original)
            echo = [0 for t in range(int(len(syllable) * echo_delay * i))]
            echo.extend([a * math.pow(echo_decay, i) for a in syllable])
            audio.extend([0 for t in range(len(echo)-len(audio))])
            audio = [audio[t] + echo[t] for t in range(len(audio))]
    except Exception as e:
        logger.debug(e)
    audio.extend([0 for t in range(length - len(audio))])
    logger.debug('length = ' + str(length))
    logger.debug('original len = ' + str(len(original)))
    audio = [audio[t] * 1.5 for t in range(length)]
    return np.array(audio[:length])

def doppler_effect(master_audio_clip, length):
    original = master_audio_clip.tolist()
    audio = []
    for i in range(doppler_stages):
        clip = original[len(original) * i/doppler_stages:len(original) * (i+1)/doppler_stages]
        clip = scipy.signal.resample(clip, int(len(clip) * (1 + max(0,i-doppler_stages/4) * 0.05)))
        audio.extend(clip)
    audio.extend([0 for t in range(length - len(audio))])
    return np.array(audio[:length])

def piecewise_fade_volume(audio, volume_profile, fade_in_len):
	
	output_audio = np.zeros(audio.shape)
	fade_in_len_samples = output_audio.size
	
	for j in range(len(volume_profile) - 1):
		start_dbeat, start_volume = volume_profile[j]
		end_dbeat, end_volume = volume_profile[j+1]
		start_idx = int(fade_in_len_samples * float(start_dbeat) / fade_in_len)
		end_idx = int(fade_in_len_samples * float(end_dbeat) / fade_in_len)
		audio_to_fade = audio[start_idx:end_idx]
		output_audio[start_idx:end_idx] = linear_fade_volume(audio_to_fade, start_volume=start_volume, end_volume=end_volume)
	
	return output_audio
	
def piecewise_lin_fade_filter(audio, filter_type, profile, fade_in_len):
	
	output_audio = np.zeros(audio.shape)
	fade_in_len_samples = audio.size
	
	for j in range(len(profile) - 1):
		start_dbeat, start_volume = profile[j]
		end_dbeat, end_volume = profile[j+1]
		start_idx = int(fade_in_len_samples * float(start_dbeat) / fade_in_len)
		end_idx = int(fade_in_len_samples * float(end_dbeat) / fade_in_len)
		audio_to_fade = audio[start_idx:end_idx]
		output_audio[start_idx:end_idx] = linear_fade_filter(audio_to_fade, filter_type, start_volume=start_volume, end_volume=end_volume)
	
	return output_audio

def linear_fade_volume(audio, start_volume=0.0, end_volume=1.0):
	if start_volume == end_volume == 1.0:
		return audio
		
	length = audio.size
	profile = np.sqrt(np.linspace(start_volume, end_volume, length))
	return audio * profile

def linear_fade_filter(audio, filter_type, start_volume=0.0, end_volume=1.0):
	
	if start_volume == end_volume == 1.0:
		return audio
	
	SAMPLE_RATE = 44100
	LOW_CUTOFF = 70
	MID_CENTER = 1000
	HIGH_CUTOFF = 13000
	Q = 1.0 / np.sqrt(2)
	NUM_STEPS = 20 if start_volume != end_volume else 1
	
	bquad_filter = yodel.filter.Biquad()
	length = audio.size		# Assumes mono audio
	
	profile = np.linspace(start_volume, end_volume, NUM_STEPS)
	output_audio = np.zeros(audio.shape)
	
	for i in range(NUM_STEPS):
		start_idx = int((i / float(NUM_STEPS)) * length)
		end_idx = int(((i + 1) / float(NUM_STEPS)) * length)
		if filter_type == 'low_shelf':
			bquad_filter.low_shelf(SAMPLE_RATE, LOW_CUTOFF, Q, -int(26 * (1.0 - profile[i])))
		elif filter_type == 'high_shelf':
			bquad_filter.high_shelf(SAMPLE_RATE, HIGH_CUTOFF, Q, -int(26 * (1.0 - profile[i])))
		else:
			raise Exception ('Unknown filter type: ' + filter_type)
		#~ bquad_filter.process(audio[start_idx : end_idx], output_audio[start_idx : end_idx]) # This was too slow, code beneath is faster!
		b = bquad_filter._b_coeffs
		a = bquad_filter._a_coeffs
		a[0] = 1.0 # Normalizing the coefficients is already done in the yodel object, but a[0] is never reset to 1.0 after division!
		output_audio[start_idx : end_idx] = scipy.signal.lfilter(b, a, audio[start_idx : end_idx]).astype('float32')
	
	return output_audio

class TransitionProfile:
	
	def __init__(self, len_dbeats, volume_profile, low_profile, high_profile):
		'''
			This class represents a transition profile during a fade.
			It takes three profiles as input. A profile is a sequence of tuples in the following format:
			[(queue_dbeat_1,volume_fraction_1),(queue_dbeat_2,volume_fraction_2),...]
			For example:
			[(0,0.0), (1,0.5), (7, 0.5), (8, 1.0)] is a transition like this:
					     ____
			            /
			     -------
			____/
			
			The first downbeat must always be 0 and the last must always be length_dbeats
			The profile must also be non-decreasing in downbeat number
			The fractions must be between 0.0 and 1.0
			
			:len_dbeats		The length of the transition in downbeats
			:volume_profile	The profile 
		'''
		if not ((volume_profile[0][0] == low_profile[0][0] == high_profile[0][0] == 0) \
			 and (volume_profile[len(volume_profile)-1][0] == low_profile[len(low_profile)-1][0] == high_profile[len(high_profile)-1][0] == len_dbeats)):
				 raise Exception ('Profiles must start at downbeat 0 and end at downbeat len_dbeats')
		i_prev = -1
		for i, v in volume_profile:
			if not i_prev <= i:
				logger.debug(volume_profile)
				raise Exception ('Profiles must be increasing in downbeat indices')
			if not (v >= 0.0 and v <= 1.0):
				raise Exception ('Profile values must be between 0.0 and 1.0')
			i_prev = i
		i_prev = -1
		for i, v in low_profile:
			if not i_prev <= i:
				raise Exception ('Profiles must be increasing in downbeat indices')	
			if not (v >= -1.0 and v <= 1.0):
				raise Exception ('Profile values must be between 0.0 and 1.0')	
			i_prev = i
		i_prev = -1
		for i, v in high_profile:
			if not i_prev <= i:
				raise Exception ('Profiles must be increasing in downbeat indices')
			if not (v >= -1.0 and v <= 1.0):
				raise Exception ('Profile values must be between 0.0 and 1.0')
			i_prev = i
		self.len_dbeats = len_dbeats
		self.volume_profile = volume_profile
		self.low_profile = low_profile
		self.high_profile = high_profile
		
	def apply(self, audio, fade_len=None):
	        if fade_len is not None:
                    self.len_dbeats = fade_len
                    
		output_audio = np.copy(audio)
		fade_in_len = self.len_dbeats
				
		low_profile = self.low_profile			
		output_audio = piecewise_lin_fade_filter(output_audio, 'low_shelf', low_profile, fade_in_len)
		
		high_profile = self.high_profile
		output_audio = piecewise_lin_fade_filter(output_audio, 'high_shelf', high_profile, fade_in_len)
		
		volume_profile = self.volume_profile
		output_audio = piecewise_fade_volume(output_audio, volume_profile, fade_in_len)	
		
		return output_audio

        def echo(self, time_points):
                self.high_profile = zip(time_points, [1.0, 1.0, 1.0, 1.0, 1.0, 0.5, -1.0])   
                self.low_profile = zip(time_points, [1.0, 1.0, 1.0, 1.0, 1.0, 0.5, -1.0])
                self.volume_profile = zip(time_points, [1.0, 1.0, 1.0, 1.0, 1.0, 0.6, 0.0])
        
        def delay(self, time_points):
                self.volume_profile = zip(time_points, [0.0, 0.0, 0.1, 0.6, 1.0, 1.0, 1.0])
                self.low_profile = zip(time_points, [-1.0, -1.0, -0.9, -0.2, 1.0, 1.0, 1.0])
                self.high_profile = zip(time_points, [-1.0, -1.0, -0.9, -0.2, 1.0, 1.0, 1.0])

        def enter(self, time_points):
                self.high_profile = zip(time_points, [-1.0, -1.0, 0.5, 1.0, 1.0, 1.0, 1.0])
                self.low_profile = zip(time_points, [-1.0, 0.0, 1.0, 1.0, 1.0, 1.0, 1.0])
                self.volume_profile = zip(time_points, [0.0, 0.5, 1.0, 1.0, 1.0, 1.0, 1.0])
	
class CrossFade:
	
	'''
		Represents a crossfade where both the master and the slave can be adjusted at the same time
	'''
	
	def __init__(self, queue_1, queue_2_options, len_dbeats, crossover_point, fade_type, switch_master = True):
		'''
			:queue_1		the queue point in the first song in nr of downbeats
			:queue_2		the queue point in the second song in nr of downbeats
			:fade_in_len	the length of the fade in section (after fade_in: switch master)
			:fade_out_len	the length of the fade out section
			:switch_master	false if the master before and master after the fade are the same song (song 1)
		'''
		self.queue_1 = queue_1
		self.queue_2_options = queue_2_options
		self.len_dbeats = len_dbeats
		self.crossover_point = crossover_point
		
		P = self.crossover_point
		L = len_dbeats
		if P < 2 or L-P < 2:
			# This is an atypical cross-fade:fade-in and/or fade-out is very short!
			if P < 0:
				# This is a bugfix, sometimes the crossover point is 0 apparently!
				logger.warning('Crossover point is negative!')
				P = L/2
			
			time_points = [0, P, P, L]
			master_vol_profile = zip(time_points, 	[1.0, 1.0, 0.8, 0.0])
			master_low_profile = zip(time_points, 	[1.0, 1.0, -1.0, -1.0])
			master_high_profile = zip(time_points, 	[1.0, 1.0, -1.0, -1.0])
			slave_vol_profile = zip(time_points, 	[0.0, 0.8, 1.0, 1.0])
			slave_low_profile = zip(time_points, 	[-1.0, -1.0, 1.0, 1.0])
			slave_high_profile = zip(time_points, 	[-1.0, -1.0, 1.0, 1.0])
                        self.time_points = None
		
		else:
			if fade_type == tracklister.TYPE_ROLLING or fade_type == tracklister.TYPE_DOUBLE_DROP:
				time_points = [0, 1, P/2, P, P+1, P+(L-P)/2, L]
				master_vol_profile = zip(time_points, 	[1.0, 1.0, 0.8, 0.2, 0.1, 0.0, 0.0])
				master_low_profile = zip(time_points, 	[1.0, 1.0, 0.9, -0.4, -0.8, -1.0, -1.0])
				master_high_profile = zip(time_points, 	[1.0, 1.0, 0.9, -0.3, -0.8, -1.0, -1.0])
				slave_vol_profile = zip(time_points, 	[0.0, 0.0, 0.1, 0.6, 1.0, 1.0, 1.0])
				slave_low_profile = zip(time_points, 	[-1.0, -1.0, -0.9, -0.2, 1.0, 1.0, 1.0])
				slave_high_profile = zip(time_points, 	[-1.0, -1.0, -0.9, -0.2, 1.0, 1.0, 1.0])
                                self.time_points = time_points
			else:
				P = self.crossover_point
				L = len_dbeats
				time_points = [0, P/2, P, P+1, P+(L-P)/2, L]
				master_vol_profile = zip(time_points, 	[1.0, 0.9, 0.9, 0.8, 0.2, 0.0])
				master_low_profile = zip(time_points, 	[1.0, 0.9, 0.1, -0.5, -1.0, -1.0])
				master_high_profile = zip(time_points, 	[1.0, 1.0, 1.0, -0.4, -1.0, -1.0])
				slave_vol_profile = zip(time_points, 	[0.0, 0.1, 0.2, 0.8, 1.0, 1.0])
				slave_low_profile = zip(time_points, 	[-1.0, -1.0, 0.3, 1.0, 1.0, 1.0])
				slave_high_profile = zip(time_points, 	[-1.0, -1.0, -0.3, 0.8, 1.0, 1.0])
                                self.time_points = time_points
				
		master_profile = TransitionProfile(self.len_dbeats, master_vol_profile, master_low_profile, master_high_profile)
		slave_profile = TransitionProfile(self.len_dbeats, slave_vol_profile, slave_low_profile, slave_high_profile)
		
		self.master_profile = master_profile
		self.slave_profile = slave_profile
                self.master_volume_profile = master_vol_profile

	def apply(self, master_audio, new_audio, tempo, effect = None):
	
		'''
			Applies this transition, i.e. the low, mid and high profiles, to the input audio.
			The master song is faded out, and the new audio is faded in.
			
			:master_audio 	The master audio, which should be cropped so that the first queue point is the first sample in this buffer
			:new_audio		The new audio to be mixed with the master audio
		'''
		
		if self.master_profile == None or self.slave_profile == None:
			raise Exception('Master and slave profile must be set. Call optimize(...) before applying!')
		
		output_audio = master_audio # shallow copy
                fade_len = self.slave_profile.len_dbeats

                # produce effects accordings to probabilities
                dice = random.random()
                if (effect == 'low_pass_echo' or (effect is None and dice < low_pass_echo_prob)) and self.time_points is not None:
                    USE_EFFECT = True
                    try:
                        logger.debug('\napplying low pass echo effect\n')
                        onset = max(0, int(44100 * 4 * 60 / tempo * (fade_len * 1/4)))
                        shut = max(0, int(44100 * 4 * 60 / tempo * (fade_len * 1/4 + echo_span)))
                        logger.debug('fade_len = ' + str(fade_len))
                        output_audio[onset:] = low_pass_echo_effect(master_audio[onset:shut], len(master_audio) - onset)
                        logger.debug(str(output_audio.shape[0]))
                        self.master_profile.echo(self.time_points)
                        #self.slave_profile.delay(self.time_points)
                    except Exception as e:
                        logger.debug(e)
                elif (effect == 'doppler' or (effect is None and dice < doppler_prob + low_pass_echo_prob)) and self.time_points is not None:
                    USE_EFFECT = True
                    logger.debug('\napplying doppler effect\n')
                    onset =  max(0, int(44100 * 4 * 60 / tempo * (int(fade_len * 1/4) - doppler_span)))
                    shut = max(0, int(44100 * 4 * 60 / tempo * (int(fade_len * 1/4))))
                    logger.debug('fade_len = ' + str(fade_len))
                    output_audio[onset:] = doppler_effect(master_audio[onset:shut], len(master_audio) - onset)
                    self.master_profile.echo(self.time_points)
                elif (effect == 'low_pass_enter' or (effect is None and dice < doppler_prob + low_pass_echo_prob + low_pass_enter_prob)) and self.time_points is not None:
                    USE_EFFECT = True
                    logger.debug('\napplying low pass enter\n')
                    onset =  0
                    shut = max(0, int(44100 * 4 * 60 / tempo * math.ceil(low_pass_enter_span * 4/3)))
                    logger.debug('fade_len = ' + str(fade_len))
                    new_audio[:shut] = low_pass_enter(new_audio[onset:shut], shut-onset)
                    self.slave_profile.enter(self.time_points)
                elif (effect == 'high_pass_drag' or (effect is None and dice < doppler_prob + low_pass_echo_prob + low_pass_enter_prob + high_pass_drag_prob)) and self.time_points is not None:
                    USE_EFFECT = True
                    logger.debug('\napplying high pass drag\n')
                    onset = max(0, int(44100 * 4 * 60 / tempo * fade_len * 1/4))
                    shut = max(0, int(44100 * 4 * 60 / tempo * fade_len * 3/4))
                    logger.debug('fade_len = ' + str(fade_len))
                    logger.debug(str(shut-onset))
                    logger.debug(str(len(master_audio)))
                    output_audio[onset:shut] = high_pass_drag(master_audio[onset:shut], shut-onset)
                    #self.master_profile.echo(self.time_points)
                elif (effect == 'high_pass_echo' or (effect is None and dice < doppler_prob + low_pass_echo_prob + low_pass_enter_prob + high_pass_drag_prob + high_pass_echo_prob)) and self.time_points is not None:
                    USE_EFFECT = True
                    try:
                        logger.debug('\napplying high pass echo effect\n')
                        onset = max(0, int(44100 * 4 * 60 / tempo * (fade_len * 1/4)))
                        shut = max(0, int(44100 * 4 * 60 / tempo * (fade_len * 1/4 + echo_span)))
                        logger.debug('fade_len = ' + str(fade_len))
                        output_audio[onset:] = high_pass_echo_effect(master_audio[onset:shut], len(master_audio) - onset)
                        logger.debug(str(output_audio.shape[0]))
                        self.master_profile.echo(self.time_points)    
                    except Exception as e:
                        logger.debug(e)
                else:
                    USE_EFFECT = False
                    logger.debug('\nusing normal transition\n')
		# Calculate the necessary offsets
		fade_len_samples = int(fade_len * (60.0/tempo) * 4 * 44100 )
		
		# Perform the fade-out of the master audio first (not yet overlapped with rest of new_audio)
	        master_audio_fadeout = master_audio[:fade_len_samples]
                logger.debug(str(fade_len_samples))
                logger.debug(str(master_audio_fadeout.shape[0]))
                logger.debug(str(master_audio.shape[0]))
        	output_audio[:fade_len_samples] = self.master_profile.apply(master_audio_fadeout, fade_len)
		output_audio[fade_len_samples:] = 0
		
                fade_len_samples = min(fade_len_samples, output_audio.shape[0])

		# Current situation:
		#			|q1		 |q2		|end
		# MASTER:	===========------....
		# SLAVE:	nothing yet
		
		# Perform the fade-in and add it to the faded out master audio
                new_audio_fadein = new_audio[:fade_len_samples]
		new_audio_rest = new_audio[fade_len_samples:]
		new_audio_fadein = self.slave_profile.apply(new_audio_fadein)
		output_audio[:fade_len_samples] = output_audio[:fade_len_samples] + new_audio_fadein 
		
		# Current situation:
		#			|q1		 |q2		|end
		# MASTER:	===========------....
		# SLAVE:	.....----============
		
		output_audio = output_audio[:fade_len_samples]
		output_audio = np.append(output_audio, new_audio_rest)
                return output_audio
		# Current situation:
		#			|q1		 |q2		|end
		# MASTER:	===========------....
		# SLAVE:	.....----==========================
		
		# Apply (self-invented) loudness balancing
		loudness_balance_profile = np.zeros(fade_len_samples)
		for j in range(len(self.master_profile.volume_profile) - 1):
			# Get the positions in the audio array and the start and end volumes
                        start_dbeat, start_volume_master = self.master_profile.volume_profile[j]
                        end_dbeat, end_volume_master = self.master_profile.volume_profile[j+1]
                        start_dbeat, start_volume_slave = self.slave_profile.volume_profile[j]
			end_dbeat, end_volume_slave = self.slave_profile.volume_profile[j+1]
			# Select the correct part of the audio corresponding to this segment
                        fade_len = self.slave_profile.len_dbeats
                        start_idx = int(fade_len_samples * float(start_dbeat) / fade_len)
			end_idx = int(fade_len_samples * float(end_dbeat) / fade_len)
			# Calculate the loudness profile of this part using the formula:
			# beta = sqrt(v1^2 + v2^2)
                        master_vol_profile = linear_fade_volume(np.ones(end_idx - start_idx), start_volume_master, end_volume_master)
			slave_vol_profile = linear_fade_volume(np.ones(end_idx - start_idx), start_volume_slave, end_volume_slave)
                        loudness_balance_profile[start_idx:end_idx] = np.sqrt(1.0 / (master_vol_profile**2 + slave_vol_profile**2))
		output_audio[:fade_len_samples] *= loudness_balance_profile	
		return output_audio
