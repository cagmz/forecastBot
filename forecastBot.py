#!/usr/bin/env python

"""
A Reddit bot that delivers the weather forecast for a valid city and state.

Stuff that I need to do:
    - Set instance variable for # of days to forecast (default 5)
    - Exception handling for several methods
    - and more

To fix:
    - Full 10-day forecast table doesn't show up on some subreddits with custom CSS styles
"""

__author__ = 'Carlos Adrian Gomez'

import praw
from praw.helpers import comment_stream
import os.path
import sqlite3
import re
import requests
import random
import time

user_agent = "forecastBot by /u/cagomez"
reddit = praw.Reddit(user_agent=user_agent)

username = open("un.txt", "r").read().rstrip()
password = open("pw.txt", "r").read().rstrip()
reddit.login(username=username, password=password)

wul_api_key = open("wul.txt", "r").read().rstrip()

database_filename = "comments.db"
is_new_database = not os.path.isfile(database_filename)

CALL_TO_ACTION = "forecastbot!"

# list of subreddits to lurk
searchable_subs = ["all"]


def set_subreddit():
    return random.choice(searchable_subs)


def format_forecast(location, raw_json_forecast):
    city_str = location.pop(0)
    state_str = location.pop()

    if 'error' in raw_json_forecast['response']:
        # if the json object has an error key, then the location wasn't found
        markup_forecast = "Sorry, " + city_str + ", " + state_str + ", was not found."
    elif 'results' in raw_json_forecast['response']:
        # the json object will have a results key if there is more than 1 match for the location
        markup_forecast = "Sorry, " + city_str + ", " + state_str + " produces too many results. " \
                                                                    "Can you be more specific?"
    else:
        # else the json object contains only 1 valid result
        markup_forecast = "Your 10 day weather forecast for {city}, {state} is: " \
                          "\n\n ".format(city=city_str, state=state_str)
        markup_forecast += "\n| "
        # add days and dates
        for day in raw_json_forecast['forecast']['simpleforecast']['forecastday']:
            markup_forecast += ((day['date']['weekday_short']) + " "
                                + str(day['date']['month']) + "/" + str(day['date']['day']) + "/"
                                + str(day['date']['year'])[2:] + " | ")

        # add pipes & hyphens to show mark the end of the column headers
        markup_forecast += "\n|---	|---	|---	|---	|---	|---	|---	|---	|---	|---	|"

        # add conditions
        markup_forecast += "\n| "
        for day in raw_json_forecast['forecast']['simpleforecast']['forecastday']:
            markup_forecast += (day['conditions']) + " |"

        # add highs
        markup_forecast += "\n|"
        for day in raw_json_forecast['forecast']['simpleforecast']['forecastday']:
            markup_forecast += "High: " + str((day['high']['fahrenheit'])) + "F |"

        # add lows
        markup_forecast += "\n|"
        for day in raw_json_forecast['forecast']['simpleforecast']['forecastday']:
            markup_forecast += "Low: " + str(day['low']['fahrenheit']) + "F | "

        # per WUL TOS, data must include attribution
        markup_forecast += "\n\n ^Data ^courtesy ^of ^Weather ^Underground, ^Inc."
        # print(markup_forecast)
    return markup_forecast


def get_weather(location):
    # location param is a list that contains city (index 0) and state code (index 1)
    state_str = location.pop()
    city_str = location.pop()

    # add items back in for use in another method
    location.insert(0, city_str)
    location.insert(1, state_str)

    # build url for a JSON request
    url = 'http://api.wunderground.com/api/{api_key}/forecast10day/q/{state_code}/{city}.json'.format(
        api_key=wul_api_key, state_code=state_str, city=city_str)

    # get response object
    response = requests.get(url)
    # store JSON in a dictionary
    json_dict = response.json()
    return json_dict


def search_for_city_state(comment_body):
    # set location list to contain "invalid". if comment doesn't contain a valid city, then
    # "invalid" will be contained in the list
    location = ["invalid", "invalid"]

    # pattern to match city, state
    pattern = "(?P<city_sub_str>(?:[A-Z]\w+\s*)+),\s(?P<state_sub_str>" \
              "AL|AK|AS|AZ|AR|CA|CO|CT|DE|DC|FM|FL|GA|GU|HI|ID|IL|IN|IA|KS|" \
              "KY|LA|ME|MH|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|MP|OH|OK|" \
              "OR|PW|PA|PR|RI|SC|SD|TN|TX|UT|VT|VI|VA|WA|WV|WI|WY)"
    # compile pattern to use with match()
    city_state_pattern = re.compile(pattern)

    # try to find matches
    match = city_state_pattern.search(comment_body)
    if match:
        location[0] = match.group("city_sub_str")
        location[1] = match.group("state_sub_str")
    return location


def contains_call(comment_body):
    result = False
    lowercase_comment = comment_body.lower()
    if lowercase_comment.find(CALL_TO_ACTION) >= 0:
        result = True
    return result


def sleep():
    time.sleep(5)
    return


with sqlite3.connect(database_filename) as comment_db:
    if is_new_database:
        print("No prior database found! Creating schema...")
        cursor = comment_db.cursor()
        cursor.execute("CREATE TABLE comments(comment_id TEXT PRIMARY KEY)")
        comment_db.commit()
    else:
        print("Comments database exists: assuming that schema exists...")

    while True:
        subreddit = reddit.get_subreddit(set_subreddit())
        for comment in comment_stream(reddit_session=reddit, subreddit=subreddit):
            print("Checking comment " + comment.id + ": " + comment.body)
            if contains_call(comment.body):
                # comment contains a call to action.
                # check to see if the comment has already been replied to
                cursor.execute('''SELECT * from comments WHERE comment_id=?''', (comment.id,))
                contains = cursor.fetchone()
                if contains is None:
                    # comment is unique, so reply to it
                    print("Called by comment #: " + comment.id + ": " + comment.body)
                    location = search_for_city_state(comment.body)
                    forecast = format_forecast(location, get_weather(location=location))
                    comment.reply(forecast)
                    print("Posted a comment:\n\n " + forecast)
                    cursor.execute("INSERT INTO comments(comment_id) VALUES (?)", (comment.id,))
                    print("Added comment " + comment.id + " to comments database.")
                    comment_db.commit()
                else:
                    print("Already replied to comment " + comment.id + ": " + comment.body)
        sleep()

comment_db.close()