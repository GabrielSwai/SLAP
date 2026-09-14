# 🎵 Surrogate Language Aligner

This project is a semi-automatic Python tool for aligning Kinande spoken tone patterns with corresponding drummed musical surrogate patterns. Instead of automatically detecting speech, transcribing Kinande, or identifying which spoken phrase matches which drumming segment, the tool assumes those steps have already been completed manually in ELAN.

The program focuses on the core alignment task of detecting high and low pitches in a selected drumming segment, matching them to a manually supplied Kinande tone pattern, and exporting the resulting alignment for analysis.

This project serves as my [Dartmouth COSC 72](https://dartmouth.smartcatalogiq.com/en/current/orc/departments-programs-undergraduate/computer-science/cosc-computer-science-undergraduate/cosc-72) final project.

## 📌 Project Overview

Musical surrogate languages use instruments such as drums, flutes, or whistles to represent aspects of spoken language. In Kinande musical surrogacy, drummed pitch patterns correspond to the tone patterns of spoken Kinande phrases.

This project is designed to make the analysis of these correspondences faster by automating the final alignment step. The user manually identifies the relevant phrase and drumming segment, then the program detects the pitch pattern of the drumming and aligns it with the word-level tone pattern of the Kinande phrase.

The current version focuses on:

- Loading a drum audio recording
- Loading an existing ELAN `.eaf` annotation file
- Extracting a manually selected drumming segment
- Detecting individual surrogate note onsets
- Classifying detected notes as high or low
- Tokenizing the Kinande phrase into word-level units
- Parsing word-level tone patterns (e.g. `Talindá háke` → `L-L-H H-L`)
- Aligning the Kinande tone patterns with the detected surrogate tones
- Flagging mismatches between spoken and surrogate tone patterns
- Adding the alignment back to ELAN

## ❌ What This Project Does Not Do

To keep the project focused and realistic, the current version does **not** attempt to:

- Automatically separate speech from drumming
- Automatically transcribe Kinande speech
- Automatically determine which Kinande phrase corresponds to which drumming segment
- Perform full speech recognition or forced alignment

Those steps are assumed to be completed manually before running the tool. In the future, I plan on implementing more of the above for a higher level of automation, as well as expand the program for a wider variety of instruments and languages.

## ▶️ Running the Aligner

The main code for this project is in `aligner.py`. Before running it, create a virtual environment, activate it, and install the required dependencies from `requirements.txt`.

### macOS/Linux

~~~bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python aligner.py
~~~

### Windows

Using Command Prompt:

~~~bash
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
python aligner.py
~~~

Using PowerShell:

~~~bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python aligner.py
~~~

## 📥 Inputs

The program expects:

- A `.wav` file containing the drummed musical surrogate recording
- An `.eaf` ELAN file containing manual annotations
- A manually selected start and end time for the relevant drumming segment
- A Kinande phrase

Example phrase input:

```text
Asá hano!
```

In this format, each word corresponds to one tone pattern:

```text
Asá   → L-H
hano! → L-L
```

## 📤 Outputs

The program produces:
- An updated ELAN `.eaf` file with the alignment added to a specified tier
- Confidence information for checking the quality of the alignment

## 📁 Folder Structure

```text
surrogate-music-tone-aligner/
├── data/
│   ├── sample1.wav
│   ├── sample1.eaf
│   ├── sample2.wav
│   ├── sample2.eaf
│   ├── sample3.wav
│   └── sample3.eaf
├── outputs/
│   └── aligned_output.eaf
├── .gitignore
├── LICENSE
├── README.md
├── aligner.py
└── requirements.txt
```
