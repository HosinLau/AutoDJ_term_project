# Copyright 2017 Len Vande Veire, IDLab, Department of Electronics and Information Systems, Ghent University
# This file is part of the source code for the Auto-DJ research project, published in Vande Veire, Len, and De Bie, Tijl, "From raw audio to a seamless mix: an artificial intelligence approach to creating an automated DJ system.", 2018 (submitted)
# Released under AGPLv3 license.

import numpy as np
from essentia import *
from essentia.standard import Spectrum, Windowing, MelBands, FrameGenerator, Spectrum
from sklearn.metrics.pairwise import cosine_similarity
from sklearn import preprocessing

NUMBER_BANDS = 12
NUMBER_COEFF = 5

def feature_allframes(song, frame_indexer = None):
	
	audio = song.audio
	beats = song.beats
	fft_mag = song.fft_mag_1024_512
	fft_phase = song.fft_phase_1024_512
	
	# Initialise the algorithms
	w = Windowing(type = 'hann')
	spectrum = Spectrum() 		# FFT would return complex FFT, we only want magnitude
	melbands = MelBands(numberBands = NUMBER_BANDS)
	#~ mfcc = MFCC(numberBands = NUMBER_BANDS, numberCoefficients = NUMBER_COEFF)
	pool = Pool()
	
	if frame_indexer is None:
		frame_indexer = range(4,len(beats) - 1) # Exclude first frame, because it has no predecessor to calculate difference with
		
	# 13 MFCC coefficients
	# 40 Mel band energies
	#~ mfcc_coeffs = np.zeros((len(beats), NUMBER_COEFF))
	mfcc_bands = np.zeros((len(beats), NUMBER_BANDS))
	# 1 cosine distance value between every mfcc feature vector
	# 13 differences between MFCC coefficient of this frame and previous frame
	# 13 differences between MFCC coefficient of this frame and frame - 4	
	# 13 differences between the differences above	
	# Idem for mel band energies
	#~ mfcc_coeff_diff = np.zeros((len(beats), NUMBER_COEFF))
	mfcc_bands_diff = np.zeros((len(beats), NUMBER_BANDS * 4))
	
	# Step 1: Calculate framewise for all output frames
	# Calculate this for all frames where this frame, or its successor, is in the frame_indexer
	for i in [i for i in range(len(beats)) if (i in frame_indexer) or (i+1 in frame_indexer) 
		or (i-1 in frame_indexer) or (i-2 in frame_indexer) or (i-3 in frame_indexer)]:
		SAMPLE_RATE = 44100
		start_sample = int(beats[i] * SAMPLE_RATE)
		end_sample = int(beats[i+1] * SAMPLE_RATE) 
		#print start_sample, end_sample
		frame = audio[start_sample : end_sample if (start_sample - end_sample) % 2 == 0 else end_sample - 1]
		bands = melbands(spectrum(w(frame)))
		#~ bands, coeffs = mfcc(spectrum(w(frame)))
		#~ mfcc_coeffs[i] = coeffs
		mfcc_bands[i] = bands
	
	# Step 2: Calculate the cosine distance between the MFCC values
	for i in frame_indexer:
		# The norm of difference is usually very high around downbeat, because of melodic changes there!
		#~ mfcc_coeff_diff[i] = mfcc_coeffs[i+1] - mfcc_coeffs[i]
		mfcc_bands_diff[i][0*NUMBER_BANDS : 1*NUMBER_BANDS] = mfcc_bands[i+1] - mfcc_bands[i]
		mfcc_bands_diff[i][1*NUMBER_BANDS : 2*NUMBER_BANDS] = mfcc_bands[i+2] - mfcc_bands[i]
		mfcc_bands_diff[i][2*NUMBER_BANDS : 3*NUMBER_BANDS] = mfcc_bands[i+3] - mfcc_bands[i]
		mfcc_bands_diff[i][3*NUMBER_BANDS : 4*NUMBER_BANDS] = mfcc_bands[i] - mfcc_bands[i-1]
			
	# Include the MFCC coefficients as features
	result = mfcc_bands_diff[frame_indexer]
	#~ result = np.append(mfcc_coeff_diff[frame_indexer], mfcc_bands_diff[frame_indexer], axis=1)
	#~ print np.shape(result), np.shape(mfcc_coeff_diff), np.shape(mfcc_bands_diff)
	return preprocessing.scale(result)
