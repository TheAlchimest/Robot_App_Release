py -3.10 -m venv .venv  
.venv\Scripts\Activate
pip install -r requirements.txt

python main.py --allow_wake_word=False --device=windows --eye_model=track

python main.py --allow_interruption --device=windows --eye_model=video

python main.py --allow_wake_word --device=windows --eye_model=video

python main.py --allow_wake_word=False --device=windows --eye_model=video




