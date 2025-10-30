py -3.10 -m venv .venv  
.venv\Scripts\Activate
source .venv/bin/activate

pip install -r requirements.txt

python main.py --allow_wake_word=False --device=windows --eye_model=track

python main.py --allow_interruption --device=windows --eye_model=video

python main.py --allow_wake_word --device=windows --eye_model=video

python main.py --allow_wake_word=False --device=windows --eye_model=video


### raspberrypi
pi@raspberrypi:~/apps/Robot_App_Release $ git clone https://github.com/TheAlchimest/Robot_App_Release.git

pi@raspberrypi:~ $ cd /home/pi/apps/Robot_App_Release
pi@raspberrypi:~/apps/Robot_App_Release $ python -m venv .venv
pi@raspberrypi:~/apps/Robot_App_Release $ source .venv/bin/activate					
pi@raspberrypi:~/apps/Robot_App_Release $ pip install -r requirements.txt

pi@raspberrypi:~/apps/Robot_App_Release $ python main.py --allow_wake_word=False --device=raspi5 --eye_model=none
pi@raspberrypi:~/apps/Robot_App_Release $ git pull






