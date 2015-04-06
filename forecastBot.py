#!/usr/bin/env python

"""
A reddit bot that crawls subreddits for comments containing a city and state (e.g. Sometown, CA),
checks to see if it's valid, and then posts a reply with the weather forecast.

Stuff that I need to do:
    - Track comments that have been replied to (don't reply to the same comment)
    - Create a do-not-reply list (for botphobes)
    - Exception handling for several methods
    - and more
	
To fix:
	- Full forecast table doesn't show up on some subreddits with custom CSS styles
"""

__author__ = 'Carlos Adrian Gomez'

import praw
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

# list of subreddits to lurk
searchable_subs = ["travel", "camping"]


def set_subreddit():
    return random.choice(searchable_subs)


def format_forecast(location, raw_json_forecast):
    city_str = location.pop(0)
    state_str = location.pop()

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


def search_for_valid_city_state(comment):
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
    match = city_state_pattern.search(comment)
    if match:
        city = match.group("city_sub_str")
        state = match.group("state_sub_str")
        # try to validate potential city, state with is_valid_location()
        if is_valid_location(city, state) is True:
            # if city, state are valid, replace "invalid" in list with city and state
            location[0] = city
            location[1] = state
    return location


def is_valid_location(city_str, state_str):
    city_str = city_str.replace(" ", "%20")     # URL encode city

    # build URL for SBA API
    url = 'http://api.sba.gov/geodata/all_links_for_city_of/{city}/{state_code}.json'.format(
        city=city_str, state_code=state_str)

    # get response
    response = requests.get(url)
    # populate dictionary with decoded JSON
    json_dictionary = response.json()
    if not json_dictionary:                     # if dictionary is empty, then API couldn't find the city
        result = False
    else:
        result = True
    return result


def sleep():
    time.sleep(5)
    return


# main
while True:
    subreddit = reddit.get_subreddit(set_subreddit())
    for submission in subreddit.get_new(limit=25):
        print(submission)
        flat_comments = praw.helpers.flatten_tree(submission.comments)
        for comment in flat_comments:
            if not hasattr(comment, 'body'):
                continue
            location = search_for_valid_city_state(comment.body)
            if location[-1] is not "invalid":
                forecast = format_forecast(location, get_weather(location=location))
                comment.reply(forecast)
                print("Posted a comment:\n\n " + forecast)
                sleep()
    sleep()



