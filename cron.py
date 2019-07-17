import redis
import mysql.connector
from mysql.connector import errorcode
import time
import requests
import os

# Akatsuki-cron-py version number.
VERSION = 1.19

# Console colours
CYAN		= '\033[96m'
MAGENTA     = '\033[95m'
GREEN 		= '\033[92m'
RED 		= '\033[91m'
ENDC 		= '\033[0m'

# Initalize values as None for now.
SQL_HOST, SQL_USER, SQL_PASS, SQL_DB, WEBHOOK, WEBHOOK_GENERAL = [None] * 6

# Config.
config = open(os.path.dirname(os.path.realpath(__file__)) + '/config.ini', 'r')
config_contents = config.read().split("\n")
for line in config_contents:
    line = line.split("=")
    if line[0].strip() == "SQL_HOST": # IP Address for SQL.
        SQL_HOST = line[1].strip()
    elif line[0].strip() == "SQL_USER": # Username for SQL.
        SQL_USER = line[1].strip()
    elif line[0].strip() == "SQL_PASS": # Password for SQL.
        SQL_PASS = line[1].strip()
    elif line[0].strip() == "SQL_DB": # DB name for SQL.
        SQL_DB = line[1].strip()
    elif line[0].strip() == "WEBHOOK": # Webhook for logging.
        WEBHOOK = line[1].strip()
    else: # Config value is unknown. continue iterating anyways.
        continue

# Redis
r = redis.Redis(host='localhost', port=6379, db=0)

# MySQL
try:
    cnx = mysql.connector.connect(
        user       = SQL_USER,
        password   = SQL_PASS,
        host       = SQL_HOST,
        database   = SQL_DB,
        autocommit = True)
except mysql.connector.Error as err:
    if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
        print(f"{RED}Something is wrong with your username or password.{ENDC}")
    elif err.errno == errorcode.ER_BAD_DB_ERROR:
        print(f"{RED}Database does not exist.{ENDC}")
    else:
        print(f"{RED}{err}{ENDC}")
else:
    SQL = cnx.cursor()


def calculateRanks(): # Calculate hanayo ranks based off db pp values.
    print(f"{CYAN}-> Calculating ranks for all users in all gamemodes.{ENDC}")
    start_time_ranks = time.time()

    tables = ["rx", "users"]

    gamemodes = ["std", "taiko", "ctb", "mania"]

    for table in tables:
        print(f"Calculating {'Relax' if table == 'rx' else 'Vanilla'}.")
        for gamemode in gamemodes:
            print(f"Mode: {gamemode}")

            SQL.execute("SELECT {t}_stats.id, {t}_stats.pp_{gm}, {t}_stats.country FROM {t}_stats WHERE {t}_stats.pp_{gm} > 0 ORDER BY pp_{gm} DESC".format(t=table, gm=gamemode))
            resp = SQL.fetchall()

            for column in resp:
                userID  = column[0]
                pp      = column[1]
                country = column[2].lower()

                r.zadd(f"ripple:{'relax' if table == 'rx' else 'leader'}board:{gamemode}", int(userID), float(pp))

                if country and country != "xx":
                    r.zincrby("hanayo:country_list", country, 1)
                    r.zadd(f"ripple:{'relax' if table == 'rx' else 'leader'}board:{gamemode}:{country}", int(userID), float(pp))

    print(f"{GREEN}-> Successfully completed rank calculations.\n{MAGENTA}Time: {round((time.time() - start_time_ranks), 2)} seconds.{ENDC}")
    return True


def updateTotalScores(): # Update the main page values for total scores.
    print(f"{CYAN}-> Updating total score values.{ENDC}")
    start_time_totalscores = time.time()

    # Vanilla.
    SQL.execute("SELECT SUM(playcount_std) + SUM(playcount_taiko) + SUM(playcount_ctb) + SUM(playcount_mania) FROM users_stats WHERE 1")
    r.set("ripple:submitted_scores", str(round(int(SQL.fetchone()[0]) / 1000000, 2)) + "m")

    # Relax.
    SQL.execute("SELECT SUM(playcount_std) + SUM(playcount_taiko) + SUM(playcount_ctb) + SUM(playcount_mania) FROM rx_stats WHERE 1")
    r.set("ripple:submitted_scores_relax", str(round(int(SQL.fetchone()[0]) / 1000000, 2)) + "m")

    print(f"{GREEN}-> Successfully completed updating total score values.\n{MAGENTA}Time: {round((time.time() - start_time_totalscores), 2)} seconds.{ENDC}")
    return True


def removeExpiredDonorTags(): # Remove supporter tags from users who no longer have them owo.
    print(f"{CYAN}-> Cleaning expired donation perks and badges.{ENDC}")
    start_time_donortags = time.time()

    SQL.execute("SELECT id, username, privileges FROM users WHERE privileges & 4 AND donor_expire < %s", [int(time.time())])
    expired_donors = SQL.fetchall()

    for user in expired_donors:
        donor_type = user[2] & 8388608

        print(f"Removing {user[1]}'{'s' if user[1].endswith('s') else ''} {'Premium' if donor_type else 'Supporter'}.")

        if donor_type:
           SQL.execute("UPDATE users SET privileges = privileges - 8388612 WHERE id = %s", [user[0]])
        else:
           SQL.execute("UPDATE users SET privileges = privileges - 4 WHERE id = %s", [user[0]])

        SQL.execute("SELECT id FROM user_badges WHERE badge IN (59, 36) AND user = %s", [user[0]])
        badges = SQL.fetchall()

        for badge in badges:
            SQL.execute("DELETE FROM user_badges WHERE id = %s", [badge[0]])

    # Grab a count of the expired badges to print.
    # TODO: make this use SQL.rowcount or w/e its called. I know it exists.
    SQL.execute("SELECT COUNT(*) FROM user_badges LEFT JOIN users ON user_badges.user = users.id WHERE user_badges.badge in (59, 36) AND users.donor_expire < %s", [int(time.time())])
    expired_badges = SQL.fetchone()[0]

    # Wipe expired badges.
    SQL.execute("DELETE user_badges FROM user_badges LEFT JOIN users ON user_badges.user = users.id WHERE user_badges.badge in (59, 36) AND users.donor_expire < %s", [int(time.time())])

    print(f"{GREEN}-> Successfully cleaned {len(expired_donors)} expired donor tags and {expired_badges} expired badges.\n{MAGENTA}Time: {round((time.time() - start_time_donortags), 2)} seconds.{ENDC}")
    return True


def addSupporterBadges(): # This is retarded please cmyui do this properly in the future TODO fucking hell.
    print(f"{CYAN}-> Adding supportation badges.{ENDC}")
    start_time_supporterbadges = time.time()

    SQL.execute("UPDATE users_stats LEFT JOIN users ON users_stats.id = users.id SET users_stats.can_custom_badge = 1, users_stats.show_custom_badge = 1 WHERE users.donor_expire > %s", [int(time.time())])
    print(f"{GREEN}-> Successfully supportated.\n{MAGENTA}Time: {round((time.time() - start_time_supporterbadges), 2)} seconds.{ENDC}")
    return True


if __name__ == "__main__":
    print(f"{CYAN}Akatsuki's cron - v{VERSION}.{ENDC}")
    full_time_start = time.time()

    # lol this is cursed code right here
    if calculateRanks(): print()
    if updateTotalScores(): print()
    if removeExpiredDonorTags(): print()
    if addSupporterBadges(): print()

    full_execution_time = f"{round((time.time() - full_time_start), 2)} seconds."
    print(f"{GREEN}-> Cronjob execution completed.\n{MAGENTA}Time: {full_execution_time}{ENDC}")

    # Post execution success to discord.
    requests.post(WEBHOOK, timeout=5, json={
        "color": 5516472, # "Akatsuki purple"
        "username": "Akatsuki",
        "avatar_url": "https://nanahira.life/uploads/94Gl9eJXqkgn.jpg",
        "url": "https://github.com/cmyui/Akatsuki-cron-py",
        "embeds": [{
            "title": "Akatsuki's cron has executed successfully.",
            "description": f"Hanayo's leaderboards have been updated using ruri's latest values, to ensure utmost accuracy.\n\n**Execution time: {full_execution_time}**",
            "thumbnail": {
                "url": "https://nanahira.life/uploads/BgPvoXbV05Ut.png"
            },
            "image": {
                "url": "https://cdn.discordapp.com/attachments/592490140497084436/600930852293312512/Untitled-2.png"
            },
            "footer": {
                "text": f"Akatsuki's cron v{VERSION} | Open source on Github.",
                "icon_url": "https://nanahira.life/uploads/7eNFPw52mR2r.png" # TODO: center image
            }
        }]
    })