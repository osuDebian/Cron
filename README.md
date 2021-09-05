# Cron
The cron job write by Python. Based on Akatsuki's cron job and adjusted somethings.


## Features
+ Recalculate the total PP value of users in all modes and vanilla, relax
+ Recalculate ranks (all modes and vanilla, relax)
+ Update total score
+ Remove expired donor badges
+ Add donor badges
+ Calculate user total playcount


## Setup
First, install the requirements.
```
$ python3 -m pip install -r requirements.txt
```
Once that's finished, you can go ahead and make a config file, by doing:
```
$ cp ./config.sample.ini ./config.ini
$ nano config.ini
```
Then you can go ahead and change the needed stuff in there.

And the last thing you have to do, is running the cron job
```
$ python3 cron.py
```
If there's any issues during setup and runninng the cron job, feel free to post an issue <3

## Original Repo
[ORIGINAL | cmyui - Akatsuki-cron-py](https://github.com/cmyui/Akatsuki-cron-py) \
[Ainu fork | osuthailand - ainu-cron-py](https://github.com/osuthailand/ainu-cron-py)