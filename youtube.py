#!/usr/bin/python

from apiclient import discovery
from apiclient import errors
from oauth2client.tools import argparser
import threading
import tweepy
import sqlite3
import json

authFile = open('..\\youtubeAuth.json')
authStr = authFile.read()
authJson = json.loads(authStr)
authFile.close()
DEVELOPER_KEY = authJson['devkey']
YOUTUBE_API_SERVICE_NAME = authJson['servname']
YOUTUBE_API_VERSION = authJson['ver']
YOUTUBE_URL = authJson['url']

authFile = open('..\\twitterAuth.json')
authStr = authFile.read()
authJson = json.loads(authStr)
authFile.close()
TWITTER_CKEY = authJson['ckey']
TWITTER_CSECRET = authJson['csecret']
TWITTER_ATOKEN = authJson['atoken']
TWITTER_ASECRET = authJson['asecret']

#mysql details
HOSTNAME = 'localhost'
USERNAME = 'root'
PASSWORD = 'simon1234'
DB = 'youtube'

#mysql functions
def insertVideo(videoid):
    data = (videoid,)
    conn = sqlite3.connect('youtube.db')
    c = conn.cursor()
    try:
        c.execute('INSERT INTO videos (videoid) VALUES (?)', data)
        conn.commit()
    except Exception as e:
        pass
    conn.close()

def getUnprocessedVideos():
    conn = sqlite3.connect('youtube.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    result = []
    try:
        c.execute('SELECT videoid FROM videos WHERE processed = 0 ORDER BY dtadded asc LIMIT 1')
        for row in c.fetchall():
            id = row['videoid']
            result.append(id)

    except Exception as e:
        print(e)
        pass

    conn.commit()
    conn.close()

    return result

def setProcessed(videoid):
    data = (videoid,)
    conn = sqlite3.connect('youtube.db')
    c = conn.cursor()

    try:
        c.execute("UPDATE videos SET processed = 1 WHERE videoid = (?)", data)

    except Exception as e:
        print(e)
        return False

    conn.commit()
    conn.close()

#end mysql functions

#youtube search - used to populate the db
def youtube_search(options):
    youtube = discovery.build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,developerKey=DEVELOPER_KEY)

    search_response = youtube.search().list(
        q=options.q,
        part="id,snippet",
        maxResults=options.max_results,
        order=options.order,
        type="video",
        relevanceLanguage=options.lang,
        videoDefinition=options.definition,
        videoDuration=options.duration
    ).execute()

    for search_result in search_response.get("items", []):
        try:
            id = search_result['id']
            videoID = id['videoId']
            insertVideo(videoID)

        except Exception as e:
            continue

    threading.Timer(60, youtube_search, [options]).start()

#procced videos - sets prcessed flag to 1
def processVideos():
    statusUpdated = False

    while not(statusUpdated):
        try:
            videos = getUnprocessedVideos()
            if len(videos) == 0:
                break
            for videoID in videos:
                youtube = discovery.build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION,developerKey=DEVELOPER_KEY)
                thisVideo = youtube.videos().list(part="contentDetails,statistics,snippet",id=videoID).execute()
                for item in thisVideo.get("items", []):
                    stats = item['statistics']
                    snippet = item['snippet']

                    title = snippet['title']
                    views = int(stats['viewCount'])
                    likes = int(stats['likeCount'])
                    dislikes = int(stats['dislikeCount'])

                    print('\n', "views: ", views, '\n', "likes: ", likes, '\n', "dislikes: ", dislikes)
                    print("url: ", YOUTUBE_URL + videoID)

                    if views > 1000 and likes > (dislikes * 3):
                        print('eligable')
                        shareUrl = YOUTUBE_URL + videoID
                        tweet = title[:72].encode('utf-8').decode('utf-8') + "... " + shareUrl + " via @youtube"
                        print(tweet)

                        auth = tweepy.OAuthHandler(TWITTER_CKEY, TWITTER_CSECRET)
                        auth.set_access_token(TWITTER_ATOKEN, TWITTER_ASECRET)

                        api = tweepy.API(auth)
                        api.update_status(status=tweet)
                        statusUpdated = True
                    else:
                        print('too few views, or too few likes')

                setProcessed(videoID)
                print('processed: ', videoID)
        except Exception as e:
            print('problem processing video: ', e)

    threading.Timer(60*15, processVideos).start()

if __name__ == "__main__":
    #setup db
    conn = sqlite3.connect('youtube.db')
    c = conn.cursor()
    try:
        c.execute("CREATE TABLE if not exists videos (videoid int PRIMARY KEY NOT NULL, dtadded default CURRENT_TIMESTAMP NOT NULL, processed bit default 0 NOT NULL)")
        conn.commit()
    except Exception as e:
        print(e)
        pass
    conn.close()

    argparser.add_argument("--q", help="Search term", default="Python coding")
    argparser.add_argument("--max-results", help="Max results", default=50)
    argparser.add_argument("--order", help="Display Order", default="date")
    argparser.add_argument("--lang", help="Language", default="en")
    argparser.add_argument("--definition", help="Definition", default="high")
    argparser.add_argument("--duration", help="Duration", default="any")
    args = argparser.parse_args()

    try:
        processVideos()
        youtube_search(args)

    except errors.HttpError as e:
        print("An HTTP error ", e.resp.status, " occurred:\n", e.content.decode('utf-8'))