import redis
import mysql.connector
from mysql.connector import errorcode
import time
import os
import sys
from discord_webhook import DiscordWebhook, DiscordEmbed
import threading

# Akatsuki-cron-py version number.
VERSION = 1.29

# Console colours
CYAN		= '\033[96m'
MAGENTA     = '\033[95m'
YELLOW 		= '\033[93m'
GREEN 		= '\033[92m'
RED 		= '\033[91m'
ENDC 		= '\033[0m'

SQL_HOST, SQL_USER, SQL_PASS, SQL_DB, REDIS_HOST, REDIS_PORT, REDIS_PASS, REDIS_DB, DISCORD_WEBHOOK, SCHEDULE_INTERVAL_MINUTE = [None] * 10
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
    elif key == 'REDIS_HOST': REDIS_HOST = val # IP Address for REDIS.
    elif key == 'REDIS_PORT': REDIS_PORT = val # Port for REDIS.
    elif key == 'REDIS_PASS': REDIS_PASS = val # Password for REDIS.
    elif key == 'REDIS_DB': REDIS_DB = val # DB id for REDIS.
    elif key == 'DISCORD_WEBHOOK': DISCORD_WEBHOOK = val # DISCORD WEBHOOK URL
    elif key == 'SCHEDULE_INTERVAL_MINUTE': SCHEDULE_INTERVAL_MINUTE = val

if any(not i for i in [SQL_HOST, SQL_USER, SQL_PASS, SQL_DB, REDIS_HOST, REDIS_PORT, REDIS_PASS, REDIS_DB, SCHEDULE_INTERVAL_MINUTE]):
    raise Exception('Not all required configuration values could be found (SQL_HOST, SQL_USER, SQL_PASS, SQL_DB, REDIS_HOST, REDIS_PORT, REDIS_PASS, REDIS_DB, SCHEDULE_INTERVAL_MINUTE).')

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
r = None
if len(REDIS_PASS) < 1:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=int(REDIS_DB))
else:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=int(REDIS_DB), password=REDIS_PASS)


def sendWebhooks(title=None, description=None, color=None, fields=None):
    WEBHOOK_URL = []
    if len(DISCORD_WEBHOOK.split(",")) > 1:
        for url in DISCORD_WEBHOOK.split(","):
            url = url.replace(" ", "")
            WEBHOOK_URL.append(url)
    else:
        WEBHOOK_URL.append(DISCORD_WEBHOOK)
    webhook = DiscordWebhook(url=WEBHOOK_URL, username="Cron Job")
    embed = DiscordEmbed(title=title, description=description, color=color)
    embed.set_footer(text='Cron Job Logs')
    embed.set_timestamp()
    if fields != None:
        for i in fields:
            embed.add_embed_field(name=i['name'], value=i['value'], inline=i['inline'])
    webhook.add_embed(embed)
    response = webhook.execute()
    print("webhook send!")

def convertMode(mode):
    if mode == "std":
        return 0
    elif mode == "taiko":
        return 1
    elif mode == "ctb":
        return 2
    elif mode == "mania":
        return 3
    else:
        return 0

def deleteLeaderboardKeys():
    print('Deleting leaderboard keys in redis')
    for key in r.scan_iter("ripple:leaderboard*:*"):
        r.delete(key)
    return True


def calculateUserTotalPP(): # Calculate Users Total PP based off users score db.
    print(f'{CYAN}-> Calculating Users Total Performance Points for all users in all gamemodes.{ENDC}')
    t_start = time.time()
    Webhook_fields = []
    vanilla_w, relax_w = "----\n", "----\n"

    for relax in range(2):
        print(f'Calculating {"Relax" if relax else "Vanilla"}.')
        for gamemode in ['std', 'taiko', 'ctb', 'mania']:
            print(f'    Mode: {gamemode}')

            if relax and gamemode == "mania":
                continue

            SQL.execute('SELECT id FROM users WHERE privileges & 1 and id != 999;')
            for row in SQL.fetchall():
                userID = int(row[0])
                
                m = convertMode(gamemode)
                sql = "select sum(ROUND(ROUND(DD.pp) * pow(0.95,  (DD.RANKING-1)))) as pp from(SELECT ROW_NUMBER() OVER(ORDER BY pp DESC) AS RANKING, userid,pp FROM Ainu.scores"
                if relax:
                    sql += "_relax"
                sql += f" WHERE beatmap_id in (select beatmap_id from  Ainu.beatmaps where ranked >= 2) AND userid = {userID} AND play_mode = {m} AND completed = 3 LIMIT 500) as DD;"

                SQL.execute(sql)
                NEWPP = SQL.fetchone()[0]

                if NEWPP is None:
                    continue

                sql_update = "update "
                if relax:
                    sql_update += f"rx_stats set pp_{gamemode} = {NEWPP} where id = {userID}"
                    SQL.execute(f"select pp_{gamemode} from rx_stats where id = {userID}")
                else:
                    sql_update += f"users_stats set pp_{gamemode} = {NEWPP} where id = {userID}"
                    SQL.execute(f"select pp_{gamemode} from users_stats where id = {userID}")
                BEFORE_PP = SQL.fetchone()[0]

                if (NEWPP - BEFORE_PP) > 0:
                    print(f"    Calculate Done. UID[{userID}] {YELLOW}{BEFORE_PP}pp => {NEWPP}pp{ENDC}")
                elif (NEWPP - BEFORE_PP) < 0:
                    print(f"    Calculate Done. UID[{userID}] {RED}{BEFORE_PP}pp => {NEWPP}pp{ENDC}")
                if (NEWPP - BEFORE_PP) > 0 or (NEWPP - BEFORE_PP) < 0:
                    if relax:
                        relax_w += f"    {gamemode} | {userID} | {BEFORE_PP}pp => {NEWPP}pp\n"
                    else:
                        vanilla_w += f"    {gamemode} | {userID} | {BEFORE_PP}pp => {NEWPP}pp\n"
                    SQL.execute(sql_update)
                time.sleep(0.5)
            print(f'        {gamemode} Done.')
    Webhook_fields.append({"name": "Vanilla", "value": vanilla_w, "inline": False})
    Webhook_fields.append({"name": "Relax", "value": relax_w, "inline": False})
    print(f'{GREEN}-> Successfully completed Performance points calculations.\n{MAGENTA}Time: {time.time() - t_start:.2f} seconds.{ENDC}')
    sendWebhooks('Successfully completed Performance points calculations.', f'running time: {time.time() - t_start:.2f} seconds.', '6BD089', Webhook_fields)
    return True


def calculateRanks(): # Calculate hanayo ranks based off db pp values.
    print(f'{CYAN}-> Calculating ranks for all users in all gamemodes.{ENDC}')
    t_start = time.time()

    deletekey = deleteLeaderboardKeys()
    if not deletekey:
        return False

    for relax in range(2):
        print(f'Calculating {"Relax" if relax else "Vanilla"}.')
        for gamemode in ['std', 'taiko', 'ctb', 'mania']:
            print(f'    Mode: {gamemode}')

            if relax:
                SQL.execute('SELECT rx_stats.id, rx_stats.pp_{gm}, rx_stats.country FROM rx_stats LEFT JOIN users ON users.id = rx_stats.id WHERE rx_stats.pp_{gm} > 0 AND users.privileges & 1 ORDER BY pp_{gm} DESC'.format(gm=gamemode))
            else:
                SQL.execute('SELECT users_stats.id, users_stats.pp_{gm}, users_stats.country FROM users_stats LEFT JOIN users ON users.id = users_stats.id WHERE users_stats.pp_{gm} > 0 AND users.privileges & 1 ORDER BY pp_{gm} DESC'.format(gm=gamemode))

            for row in SQL.fetchall():
                userID       = int(row[0])
                pp           = float(row[1])
                country      = row[2].lower()

                if relax:
                    r.zadd(f'ripple:leaderboard_relax:{gamemode}', userID, pp)
                else:
                    r.zadd(f'ripple:leaderboard:{gamemode}', userID, pp)

                if country != 'xx':
                    r.zincrby('hanayo:country_list', country, 1)

                    r.zadd(f'ripple:leaderboard_relax:{gamemode}:{country}', userID, pp)
                    r.zadd(f'ripple:leaderboard:{gamemode}:{country}', userID, pp)

    print(f'{GREEN}-> Successfully completed rank calculations.\n{MAGENTA}Time: {time.time() - t_start:.2f} seconds.{ENDC}')
    sendWebhooks('Successfully completed rank calculations.', f'running time: {time.time() - t_start:.2f} seconds.', '007AAE')
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
    sendWebhooks('Successfully completed updating total score values.', f'running time: {time.time() - t_start:.2f} seconds.', 'D249D4')
    return True


def removeExpiredDonorTags(): # Remove supporter tags from users who no longer have them owo.
    print(f'{CYAN}-> Cleaning expired donation perks and badges.{ENDC}')
    t_start = time.time()
    Webhook_fields = []
    users_W = "-----\n"
    SQL.execute('SELECT id, username, privileges FROM users WHERE privileges & 4 AND donor_expire < %s', [int(time.time())])
    expired_donors = SQL.fetchall()

    for user in expired_donors:
        donor_type = user[2] & 8388608

        print(f"Removing {user[1]}'{'s' if user[1][-1] != 's' else ''} expired Supporter tag.")
        users_W += f"{user[1]}\n"

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
    Webhook_fields.append({"name": "Removed Suppor tag List", "value": users_W, "inline": False})
    print(f'{GREEN}-> Successfully cleaned {len(expired_donors)} expired donor tags and {expired_badges} expired badges.\n{MAGENTA}Time: {time.time() - t_start:.2f} seconds.{ENDC}')
    sendWebhooks(f'Successfully cleaned {len(expired_donors)} expired donor tags and {expired_badges} expired badges.', f'running time: {time.time() - t_start:.2f} seconds.', 'F47378', Webhook_fields)
    return True


def addSupporterBadges(): # This is retarded please cmyui do this properly in the future TODO fucking hell.
    print(f'{CYAN}-> Adding donation badges.{ENDC}')
    t_start = time.time()

    SQL.execute('UPDATE users_stats LEFT JOIN users ON users_stats.id = users.id SET users_stats.can_custom_badge = 1, users_stats.show_custom_badge = 1 WHERE users.donor_expire > %s', [int(time.time())])
    print(f'{GREEN}-> Donation badges added to users.\n{MAGENTA}Time: {time.time() - t_start:.2f} seconds.{ENDC}')
    sendWebhooks(f'Donation badges added to users.', f'running time: {time.time() - t_start:.2f} seconds.', '73EDF4')
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
                               LEFT JOIN beatmaps ON scores{ainu_mode}.beatmap_id = beatmaps.beatmap_id
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
                print(f'    {"Relax" if ainu_mode[1] else "Vanilla"} | {game_mode[0]} | {user[0]} | total_score: {total_score}, ranked_score: {ranked_score}, play_count: {playcount}')

    print(f'{GREEN}-> Successfully completed score and playcount calculations.\n{MAGENTA}Time: {time.time() - t_start:.2f} seconds.{ENDC}')
    sendWebhooks(f'Successfully completed score and playcount calculations.', f'running time: {time.time() - t_start:.2f} seconds.', 'B9D821')
    return True

def running_cron():
    print(f"{CYAN}Cronjob has been started.{ENDC}")
    t_start = time.time()
    now = time.localtime()
    now_str = f'{now.tm_year}/{now.tm_mon}/{now.tm_mday} {now.tm_hour}:{now.tm_min}:{now.tm_sec}'
    sendWebhooks(f'Cronjob has been stated.', now_str, '2139D8')
    if calculateUserTotalPP():print()
    if calculateRanks(): print()   
    if updateTotalScores(): print()    
    if removeExpiredDonorTags(): print()   
    if addSupporterBadges(): print()   
    if calculateScorePlaycount(): print()

    print(f'{GREEN}-> Cronjob execution completed.\n{MAGENTA}Time: {time.time() - t_start:.2f} seconds.{ENDC}')
    sendWebhooks(f'Cronjob execution completed.', f"running time: {time.time() - t_start:.2f} seconds.", '2139D8')

    threading.Timer((int(SCHEDULE_INTERVAL_MINUTE) * 60), running_cron).start()

if __name__ == '__main__':
    print(f"{CYAN}Akatsuki's cron - v{VERSION}.{ENDC}\nDebian Forked that osu!thailand fork Akatsuki. SO..... it is forkforked LUL :D SRY.")
    running_cron()