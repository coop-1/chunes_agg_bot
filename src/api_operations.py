import requests
import pandas as pd
import json
import pytz
import webbrowser
import time
from datetime import datetime, timedelta, timezone
from dateutil.parser import parse
from urllib.parse import urlencode

def get_guild_channels(logger, discord_base, discord_guild_id, discord_header, target_channel = None):

	guild_channels_endpoint = f'/guilds/{discord_guild_id}/channels'

	try:
		guild_channels_response = requests.get(url = f'{discord_base}/{guild_channels_endpoint}', headers = discord_header)

		logger.info(f'status code - {guild_channels_response.status_code}')

		if guild_channels_response.status_code == 200:

			for channel in json.loads(guild_channels_response.text):
			    if channel['name'] == target_channel:
			        channel_id = channel['id']

			return channel_id

		else:
			return None

	except Exception as err:
		logger.info(f'failed to retrieve discord guild channel_id - {err}')
		return None

# recursive until minimum_timestamp is less than target_date
def get_guild_channel_messages(logger, discord_base, discord_header, channel_id, target_date, min_message_id = None, minimum_timestamp = None, message_df = None):

	channel_messages_endpoint = f'/channels/{channel_id}/messages'
	# conditional payload to endpoint based on where loop is
	try:
		if minimum_timestamp == None:
			channel_messages_query = {
				'limit': 100
			}
			minimum_date = target_date
			logger.info('first_iteration')
		else:
			time.sleep(1)
			channel_messages_query = {
				'limit': 100
				,'before': min_message_id
			}
			logger.info(f'iteration - {min_message_id}')
			minimum_date = minimum_timestamp.date()

		logger.info(f'minimum_date = {minimum_date}')

		if minimum_date >= target_date:

			channel_messages_response = requests.get(url = f'{discord_base}/{channel_messages_endpoint}', headers = discord_header, params = channel_messages_query)
			logger.info(f'status code - {channel_messages_response.status_code}')
			if channel_messages_response.status_code == 200:

				# load to df and convert timestamps to et / date type
				logger.info('converting message timestamp to est and date type...')
				temp_df = pd.DataFrame(json.loads(channel_messages_response.text))
				temp_df['timestamp_et'] = temp_df['timestamp'].apply(lambda x: parse(x).astimezone(pytz.timezone('US/Eastern')))
				temp_df['date_et'] = temp_df['timestamp'].apply(lambda x: parse(x).astimezone(pytz.timezone('US/Eastern')).date())
				logger.info('message timestamp converted')

				logger.info(len(message_df))
				# check if df is empty to confirm first iteration or not
				if len(message_df) == 0:
					message_df = temp_df
					logger.info('dataframe empty - first iteration')
				else:
					logger.info('not 0')
					message_df = pd.concat([message_df, temp_df], ignore_index = True).drop_duplicates(subset = 'id')
					logger.info('dataframe from new iteration concatenated')

				minimum_timestamp = message_df['timestamp_et'].min()
				logger.info(f'minimum timestamp from this batch - {minimum_timestamp}')

				min_message_id = message_df[message_df['timestamp_et'] == minimum_timestamp]['id'].iloc[0]
				logger.info(f'minimum message_id from this batch - {min_message_id}')

				# recursion - call function with new minimum_timestamp and min_message_id
				return get_guild_channel_messages(logger, discord_base, discord_header, channel_id, target_date,
												  min_message_id = min_message_id, minimum_timestamp = minimum_timestamp,
												  message_df = message_df)

			else:
				logger.error(f'api request failed - {channel_messages_response.status_code} | {channel_messages_response.text}')
				return False
		else:
			logger.info(f'messages gathered for {target_date}')
			return message_df.to_json(orient = 'records', date_format = 'iso')

	except Exception as err:
		logger.error(f'failed to retrieve discord channel messages - {err}')
		return False

def filter_discord_messages(logger, discord_messages, target_date):
## filter to target_date only
	logger.info(f'filtering to tracks for {target_date}')
	try:
		message_df = pd.DataFrame(json.loads(discord_messages))
		# message_df['date_et'] = pd.to_datetime(message_df['date_et'], unit='ms')
		message_df['timestamp_et'] = message_df['timestamp_et'].apply(lambda x: parse(x).astimezone(pytz.timezone('US/Eastern')))
		message_df['date_et'] = message_df['timestamp'].apply(lambda x: parse(x).astimezone(pytz.timezone('US/Eastern')).date())
		# print(message_df['date_et'].head())
		# print(message_df['timestamp_et'].head())
		filtered_tracks = message_df[
			(message_df['content'].str.contains('open.spotify') == True)
			& (message_df['date_et'] >= target_date)
			]['content'].to_list()
		logger.info('tracks filtered')
		return filtered_tracks

	except Exception as err:
		logger.error(f'could not filter discord messages - {err}')
		return False

def get_spotify_access_token_refresh(logger, spotify_auth_base, spotify_refresh_token_3leg, spotify_client_creds_encoded):

	header = {
	    'Authorization': f'Basic {spotify_client_creds_encoded}'
	    ,'Content-Type': 'application/x-www-form-urlencoded'
	  }

	refresh_body = {
	    'grant_type': 'refresh_token'
	    ,'refresh_token': spotify_refresh_token_3leg
	}

	try:
		refresh_token_response = requests.post(url = f'{spotify_auth_base}/api/token', headers = header, data = refresh_body)

		logger.info(f'status code - {refresh_token_response.status_code}')

		if refresh_token_response.status_code == 200:

			return json.loads(refresh_token_response.text)['access_token']

		else:
			None

	except Exception as err:
		logger.error(f'failed to refresh spotify access token - {err}')
		return None

def upsert_spotify_track_into_playlist(logger, spotify_web_base, spotify_refreshed_access_token, discord_tracks_today, spotify_playlist_id):

	playlist_url = f'{spotify_web_base}/playlists/{spotify_playlist_id}/tracks'

	track_body = {
	    'uris': discord_tracks_today
	}

	header = {
	    'Authorization': f'Bearer {spotify_refreshed_access_token}'
	    ,'Content-Type': 'application/json'
	}

	track_list_size = len(discord_tracks_today)
	track_subset = 0
	while track_subset < track_list_size:
		logger.info(f'total track list size - {track_list_size}')

		if track_list_size - track_subset > 99:
			list_subset = discord_tracks_today[track_subset: track_subset + 99]
			delete_body = {'tracks': [{'uri': track} for track in list_subset]}
			track_body = {'uris': [track for track in list_subset]}
			logger.info(f'track subset range - {track_subset} to {track_subset + 99}')
		else:
			list_subset = discord_tracks_today[track_subset:]
			delete_body = {'tracks': [{'uri': track} for track in list_subset]}
			track_body = {'uris': [track for track in list_subset]}
			logger.info(f'track subset range - {track_subset} to {track_list_size}')

		# delete_body = {'tracks': [{'uri': track} for track in discord_tracks_today]}

		try:
			logger.info(f'deleting tracks from playlist {spotify_playlist_id}...')

			playlist_delete_response = requests.delete(url = playlist_url, headers = header, data = json.dumps(delete_body))

			logger.info(f'status code - {playlist_delete_response.status_code}')

			if playlist_delete_response.status_code != 200:
				logger.info(f'status code - {playlist_delete_response.status_code} | {playlist_delete_response.text}')
				return False

		except Exception as err1:
			logger.error(f'failed to delete tracks from playlist {spotify_playlist_id} - {err1}')
			return False

		logger.info('tracks deleted')

		try:

			logger.info(f'inserting tracks into playlist {spotify_playlist_id}...')

			playlist_insert_response = requests.post(url = playlist_url, headers = header, data = json.dumps(track_body))

			logger.info(f'status code - {playlist_insert_response.status_code}')

			if playlist_insert_response.status_code != 201:
				logger.info(f'status code - {playlist_insert_response.status_code} | {playlist_insert_response.text}')
				return False

		except Exception as err2:
			logger.error(f'failed to insert tracks into spotify playlist {spotify_playlist_id} - {err2}')
			return False

		logger.info('tracks inserted')

		track_subset += 99

	return True

def spotify_track_cleanup(logger, spotify_web_base, spotify_refreshed_access_token, spotify_target_tracks):
	tracks_unpacked = []

	logger.info('looking for albums in todays messages...')
	for track in spotify_target_tracks:

		if track.split('/')[3] == 'track':
			# parse and add to tracks_unpacked list
			tracks_unpacked.append(f"spotify:track:{track.replace('https://open.spotify.com/','').split('/')[1].split('?')[0]}")

		elif track.split('/')[3] == 'album':
			# grab album_id to request against for all tracks in album
			album_id = track.split('/')[4].split('?')[0]

			logger.info(f'unpacking album_id {album_id}...')
			try:
				album_url = f'{spotify_web_base}/albums/{album_id}/tracks'

				header = {
					'Authorization': f'Bearer {spotify_refreshed_access_token}'
					, 'Content-Type': 'application/json'
				}

				album_lookup_response = requests.get(url = album_url, headers = header)
				logger.info(f'status code - {album_lookup_response.status_code}')

				if album_lookup_response.status_code == 200:
					album_tracks = pd.DataFrame(json.loads(album_lookup_response.text)['items'])['uri'].to_list()
					tracks_unpacked = tracks_unpacked + album_tracks # concat tracks returned from album lookup to tracks_unpacked running list

				else:
					logger.error(f'status code {album_lookup_response.status_code} - {album_lookup_response.text}')
					return False

			except Exception as err:
				logger.error(f'failed to perform lookup on album {album_id} - {err}')
				return False

			logger.info(f'album {album_id} unpacking complete')

	return tracks_unpacked