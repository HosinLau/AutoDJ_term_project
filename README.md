# Auto-DJ
This repository contains the source code of the automatic DJ system developed by Len Vande Veire, under the supervision of prof. Tijl De Bie. It has been designed for Drum and Bass music, a sub-genre of Electronic Dance Music.

The system is described in more detail in the paper _Vande Veire, Len and De Bie, Tijl, "From raw audio to a seamless mix: an artificial intelligence approach to creating an automated DJ system, 2018_.

## Installing dependencies

The automatic DJ application has been developed for python 2.7.12 and tested on Ubuntu 16.04 LTS. It depends on the following python packages:
* colorlog (2.10.0)
* Essentia
* joblib (0.11)
* librosa (0.5.0)
* numpy (1.12.1)
* pyAudio (0.2.8)
* scikit-learn (0.18.1)
* scipy (0.19.0)
* yodel (0.3.0)

Installing these packages can be installed using e.g. the `pip` package manager or using `apt-get` on Ubuntu. Installation instructions for the Essentia library can be found on [http://essentia.upf.edu/documentation/installing.html](http://essentia.upf.edu/documentation/installing.html).

## Running the application

To run the application, run the `main.py` script in the `auto-dj/Application` directory:

`python main.py`

The application is controlled using commands. The following commands are available:

* `loaddir <directory>` : Add the _.wav_ and _.mp3_ audio files in the specified directory to the pool of available songs.
* `annotate` : Annotate all the files in the pool of available songs that are not annotated yet. Note that this might take a while, and that in the current prototype this can only be interrupted by forcefully exiting the program (using the key combination `Ctrl+C`).
* `play` : Start a DJ mix. This command must be called after using the \texttt{loaddir} command on at least one directory with some annotated songs. Also used to continue playing after pausing.
* `pause` : Pause the DJ mix.
* `stop` : Stop the DJ mix.
* `skip` : Skip to the next important boundary in the mix. This skips to either the beginning of the next crossfade, the switch point of the current crossfade or the end of the current crossfade, whichever comes first.
* `s` : Shorthand for the skip command
* `showannotated` : Shows how many of the loaded songs are annotated.
* `debug` : Toggle debug information output. This command must be used before starting playback, or it will have no effect.

To exit the application, use the `Ctrl+C` key combination.