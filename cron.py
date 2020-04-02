import redis
import mysql.connector
from mysql.connector import errorcode
import time
import requests
import os
import sys

# Akatsuki-cron-py version number.
VERSION = 1.29

# Console colours
CYAN		= '\033[96m'
MAGENTA     = '\033[95m'
YELLOW 		= '\033[93m'
GREEN 		= '\033[92m'
RED 		= '\033[91m'
ENDC 		= '\033[0m'

SQL_HOST, SQL_USER, SQL_PASS, SQL_DB = [None] * 4
with open(f'{os.path.dirname(os.path.realpath(__file__))}/config.ini', 'r') as f:
    conf_data = f.read().splitlines()

for _line in conf_data:
    if not _line: continue
    line = _line.split('=')
    key = line[0].rstrip()
    val = line[1].lstrip()

    if key == 'SQL_HOST': SQL_HOST = val # IP Address for SQL.
    elif key == 'SQL_USER': SQL_USER = val # Username for SQL.
    elif key == 'SQL_PASS': SQL_PASS = val # Password for SQL.
    elif key == 'SQL_DB': SQL_DB = val # DB name for SQL.

if any(not i for i in [SQL_HOST, SQL_USER, SQL_PASS, SQL_DB]):
    raise Exception('Not all required configuration values could be found (SQL_HOST, SQL_USER, SQL_PASS, SQL_DB).')

try:
    cnx = mysql.connector.connect(
        user       = SQL_USER,
        password   = SQL_PASS,
        host       = SQL_HOST,
        database   = SQL_DB,
        autocommit = True)
except mysql.connector.Error as err:
    if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
        raise Exception('Something is wrong with your username or password.')
    elif err.errno == errorcode.ER_BAD_DB_ERROR:
        raise Exception('Database does not exist.')
    else:
        raise Exception(err)
else:
    SQL = cnx.cursor()

if not SQL: raise Exception('Could not connect to SQL.')

# Redis
r = redis.Redis(host='localhost', port=6379, db=0)

def calculateRanks(): # Calculate hanayo ranks based off db pp values.
    print(f'{CYAN}-> Calculating ranks for all users in all gamemodes.{ENDC}')
    t_start = time.time()

    # do not flush as it'll break "Online Users" on hanayo.
    # r.flushall() # Flush current set (removes restricted players).
    r.delete(r.keys("ripple:leaderboard:*"))
    r.delete(r.keys("ripple:relaxboard:*"))

    for relax in range(2):
        print(f'Calculating {"Relax" if relax else "Vanilla"}.')
        for gamemode in ['std', 'taiko', 'ctb', 'mania']:
            print(f'Mode: {gamemode}')

<<<<<<< HEAD
            if relax:
                SQL.execute('SELECT rx_stats.id, rx_stats.pp_{gm}, rx_stats.country, users.latest_activity FROM rx_stats LEFT JOIN users ON users.id = rx_stats.id WHERE rx_stats.pp_{gm} > 0 AND users.privileges & 1 ORDER BY pp_{gm} DESC'.format(gm=gamemode))
            else:
                SQL.execute('SELECT users_stats.id, users_stats.pp_{gm}, users_stats.country, users.latest_activity FROM users_stats LEFT JOIN users ON users.id = users_stats.id WHERE users_stats.pp_{gm} > 0 AND users.privileges & 1 ORDER BY pp_{gm} DESC'.format(gm=gamemode))
=======
            SQL.execute('SELECT {rx}_stats.id, {rx}_stats.pp_{gm}, {rx}_stats.country, users.latest_activity FROM {rx}_stats LEFT JOIN users ON users.id = {rx}_stats.id WHERE {rx}_stats.pp_{gm} > 0 AND users.privileges & 1 ORDER BY pp_{gm} DESC'.format(rx='rx' if relax else 'users', gm=gamemode))
>>>>>>> 812eb4b83e052c20c5d31fee9663db090736f880

            currentTime = int(time.time())
            for row in SQL.fetchall():
                userID       = int(row[0])
                pp           = float(row[1])
                country      = row[2].lower()
                daysInactive = (currentTime - int(row[3])) / 60 / 60 / 24
                
                if daysInactive > 60:
                    continue

<<<<<<< HEAD
                if relax:
                    r.zadd(f'ripple:leaderboard_relax:{gamemode}', userID, pp)
                else:
                    r.zadd(f'ripple:leaderboard:{gamemode}', userID, pp)
=======
                r.zadd(f'ripple:{"relax" if relax else "leader"}board:{gamemode}', userID, pp)
>>>>>>> 812eb4b83e052c20c5d31fee9663db090736f880

                if country != 'xx':
                    r.zincrby('hanayo:country_list', country, 1)

                    r.zadd(f'ripple:leaderboard_relax:{gamemode}:{country}', userID, pp)
                    r.zadd(f'ripple:leaderboard:{gamemode}:{country}', userID, pp)

    print(f'{GREEN}-> Successfully completed rank calculations.\n{MAGENTA}Time: {time.time() - t_start:.2f} seconds.{ENDC}')
    return True


def updateTotalScores(): # Update the main page values for total scores.
    print(f'{CYAN}-> Updating total score values.{ENDC}')
    t_start = time.time()

    # Vanilla.
    SQL.execute('SELECT id FROM scores ORDER BY time DESC LIMIT 1')
    r.set('ripple:submitted_scores', f'{(SQL.fetchone()[0] - 500000000) / 1000000:.2f}m')

    # Relax.
    SQL.execute('SELECT id FROM scores_relax ORDER BY time DESC LIMIT 1')
    r.set('ripple:submitted_scores_relax', f'{SQL.fetchone()[0] / 1000000:.2f}m')

    print(f'{GREEN}-> Successfully completed updating total score values.\n{MAGENTA}Time: {time.time() - t_start:.2f} seconds.{ENDC}')
    return True


def removeExpiredDonorTags(): # Remove supporter tags from users who no longer have them owo.
    print(f'{CYAN}-> Cleaning expired donation perks and badges.{ENDC}')
    t_start = time.time()

    SQL.execute('SELECT id, username, privileges FROM users WHERE privileges & 4 AND donor_expire < %s', [int(time.time())])
    expired_donors = SQL.fetchall()

    for user in expired_donors:
        donor_type = user[2] & 8388608

        print(f"Removing {user[1]}'{'s' if user[1][-1] != 's' else ''} expired Supporter tag.")

        SQL.execute('UPDATE users SET privileges = privileges - 4 WHERE id = %s', [user[0]])

        SQL.execute('SELECT id FROM user_badges WHERE badge IN (1002) AND user = %s', [user[0]])

        for badge in SQL.fetchall():
            SQL.execute('DELETE FROM user_badges WHERE id = %s', [badge[0]])

    # Grab a count of the expired badges to print.
    # TODO: make this use SQL.rowcount or w/e its called. I know it exists.
    SQL.execute('SELECT COUNT(*) FROM user_badges LEFT JOIN users ON user_badges.user = users.id WHERE user_badges.badge in (100) AND users.donor_expire < %s', [int(time.time())])
    expired_badges = SQL.fetchone()[0]

    # Wipe expired badges.
    SQL.execute('DELETE user_badges FROM user_badges LEFT JOIN users ON user_badges.user = users.id WHERE user_badges.badge in (100) AND users.donor_expire < %s', [int(time.time())])

    print(f'{GREEN}-> Successfully cleaned {len(expired_donors)} expired donor tags and {expired_badges} expired badges.\n{MAGENTA}Time: {time.time() - t_start:.2f} seconds.{ENDC}')
    return True


def addSupporterBadges(): # This is retarded please cmyui do this properly in the future TODO fucking hell.
    print(f'{CYAN}-> Adding donation badges.{ENDC}')
    t_start = time.time()

    SQL.execute('UPDATE users_stats LEFT JOIN users ON users_stats.id = users.id SET users_stats.can_custom_badge = 1, users_stats.show_custom_badge = 1 WHERE users.donor_expire > %s', [int(time.time())])
    print(f'{GREEN}-> Donation badges added to users.\n{MAGENTA}Time: {time.time() - t_start:.2f} seconds.{ENDC}')
    return True


def calculateScorePlaycount():
    print(f'{CYAN}-> Calculating score (total, ranked) and playcount for all users in all gamemodes.{ENDC}')
    t_start = time.time()

    # Get all users in the database.
    SQL.execute('SELECT id FROM users WHERE privileges & 1 ORDER BY id ASC')
    users = SQL.fetchall()

    for ainu_mode in [['users', ''], ['rx', '_relax']]:
        print(f'Calculating {"Relax" if ainu_mode[1] else "Vanilla"}.')

        for game_mode in [['std', '0'], ['taiko', '1'], ['ctb', '2'], ['mania', '3']]:
            print(f'Mode: {game_mode[0]}')

            for user in users:
                total_score, ranked_score, playcount = [0] * 3

                # Get every score the user has ever submitted.
                # .format sql queries hahahahah fuck you i don't care
                SQL.execute('''SELECT scores{ainu_mode}.score, scores{ainu_mode}.completed, beatmaps.ranked
                               FROM scores{ainu_mode}
                               LEFT JOIN beatmaps ON scores{ainu_mode}.beatmap_md5 = beatmaps.beatmap_md5
                               WHERE
                                scores{ainu_mode}.userid = %s AND
                                scores{ainu_mode}.play_mode = {game_mode}
                               '''.format(ainu_mode=ainu_mode[1], game_mode=game_mode[1]), [user[0]])

                # Iterate through every score, appending ranked and total score, along with playcount.
                for score, completed, ranked in SQL.fetchall():
                    if score < 0: print(f'{YELLOW}Negative score: {score} - UID: {user[0]}{ENDC}'); continue # Ignore negative scores.

                    if not completed: playcount += 1; continue
                    if completed == 3 and ranked == 2: ranked_score += score
                    total_score += score
                    playcount += 1

                # Score and playcount calculations complete, insert into DB.
                SQL.execute('''UPDATE {ainu_mode}_stats
                               SET total_score_{game_mode} = %s, ranked_score_{game_mode} = %s, playcount_{game_mode} = %s
                               WHERE id = %s'''.format(
                                   ainu_mode=ainu_mode[0],
                                   game_mode=game_mode[0]
                                ), [total_score, ranked_score, playcount, user[0]]
                            )

    print(f'{GREEN}-> Successfully completed score and playcount calculations.\n{MAGENTA}Time: {time.time() - t_start:.2f} seconds.{ENDC}')
    return True


if __name__ == '__main__':
    print(f"{CYAN}Akatsuki's cron but I forked them xd - v{VERSION}.{ENDC}")
    intensive = len(sys.argv) > 1 and any(sys.argv[1].startswith(x) for x in ['t', 'y', '1'])
    t_start = time.time()
    # lol this is cursed code right here
    if calculateRanks(): print()
    if updateTotalScores(): print()
    if removeExpiredDonorTags(): print()
    if addSupporterBadges(): print()
    if intensive and calculateScorePlaycount(): print()

    print(f'{GREEN}-> Cronjob execution completed.\n{MAGENTA}Time: {time.time() - t_start:.2f} seconds.{ENDC}')
