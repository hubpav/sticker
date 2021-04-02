# Simulator: STICKER

This repository contains Python application for STICKER device simulation by HARDWARIO. It is an application with local shell simulation data for an IoT sensor. The JSON data can be sent via HTTP POST endpoint, or logged locally to a file.


## Requirements

* Git
* Python 3


## Installation

1. Open your terminal application.

2.  Clone this repository

    ```
    git clone https://github.com/hubpav/sticker.git
    ```

3. Go to the repository folder:

   ```
   cd sticker
   ```

4. Create a virtual environment:

   ```
   python3 -m venv venv
   ```

5. Activate the virtual environment:

   ```
   source venv/bin/activate
   ```

6. Install the required packages:

   ```
   python3 -m pip -r requirements.txt
   ```


## Usage

> Note: Your virtual environments with the installed dependecies has to be activated first before running. For activation, refer to the **Installation** chapter above.

To see the help:

```
python3 sticker.py --help
```

To start interactive shell with HTTP endpoint:

```
python3 sticker.py -d 123456 -i 60 -e http://localhost:5000/
```

To execute command script with file logging only:

```
python3 sticker.py -d 123456 -i 60 -s script.txt
```
