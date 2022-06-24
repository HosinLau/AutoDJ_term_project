The idea of implementing an auto-DJ music track selection and mixing system requires the combination of several MIR techniques.
In this final course project, I made some modifications and added functions to an existing open source auto-DJ project.

All commands in the original author's README file are reserved in this project. Based upon that, I provided a new command to test
and evaluate the results of the transition effects that I added.

* `assign <master_song> <slave_song> <transition_type> <transition_effect>` : Assign two songs to be concatenated, with the slave appended after the master.
Also specify one of three transition types: 'roll' (rolling), 'ddrop' (double drop), 'chill' (relax). If want for random, leave it blank.
And specify one of five transition effects: 'low_pass_echo', 'doppler', 'high_pass_echo', 'high_pass_drag', 'low_pass_enter'.
If want for random, leave it blank. If want to use normal transition without any effects, type 'normal'.

I implemented this project on a Windows Subsystem for Linux (WSL). (Ubuntu 20.04.4 LTS)
To handle some difficulties running this program on a WSL, I disabled the audio output for music playing. To re-enable music playing, 
users can uncomment the lines 198~202 in file 'djcontroller.py', specifically the function 'self.stream = self.pyaudio.open(...)'.
Even though audio output is disabled, users can still find the composed tracks in their folder. Names are 'mix{}.wav' for random continuous mixes and
'assigned{}.wav' for assigned mixes.
