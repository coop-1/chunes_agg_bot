import requests
import pandas as pd
import json
import pytz
import webbrowser
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

def get_guild_channel_messages(logger, discord_base, discord_header, channel_id, target_day = None):

	channel_messages_endpoint = f'/channels/{channel_id}/messages'
	channel_messages_query = {
	    'limit': 100
	}

	try:
		channel_messages_response = requests.get(url = f'{discord_base}/{channel_messages_endpoint}', headers = discord_header, params = channel_messages_query)

		logger.info(f'status code - {channel_messages_response.status_code}')

		if channel_messages_response.status_code == 200:

			logger.info('converting message timestamp to est and date type...')
			messages_df = pd.DataFrame(json.loads(channel_messages_response.text))
			messages_df['timestamp_et'] = messages_df['timestamp'].apply(lambda x: parse(x).astimezone(pytz.timezone('US/Eastern')))
			messages_df['date_et'] = messages_df['timestamp'].apply(lambda x: parse(x).astimezone(pytz.timezone('US/Eastern')).date())
			logger.info('message timestamp converted')

			target_day = datetime.now().date() - timedelta(days = 1) ## default to prior day if no parameter is provided

			## filter to target_date only
			logger.info(f'filtering to tracks for {target_day}')
			filtered_tracks = messages_df[
			    (messages_df['content'].str.contains('open.spotify') == True)
			    & (messages_df['date_et'] == target_day)
			    ]['content'].to_list()
			logger.info('tracks filtered')

			## clean up format to match spotify requirement for api post call
			logger.info('cleaning up format for spotify playlist insert...')
			target_tracks = [f"spotify:track:{x.replace('https://open.spotify.com/','').split('/')[1].split('?')[0]}" for x in filtered_tracks]
			logger.info('format tidied')

			return target_tracks

		else:
			return None

	except Exception as err:
		logger.error(f'failed to retrieve discord channel messages - {err}')
		return None

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

	delete_body = {'tracks': [{'uri': track} for track in discord_tracks_today]}

	try:
		logger.info(f'deleting tracks from playlist {spotify_playlist_id}...')		

		playlist_delete_response = requests.delete(url = playlist_url, headers = header, data = json.dumps(delete_body))

		logger.info(f'status code - {playlist_delete_response.status_code}')

	except Exception as err1:
		logger.error(f'failed to delete tracks from playlist {spotify_playlist_id} - {err1}')
		return None

	logger.info('tracks deleted')

	try:

		logger.info(f'inserting tracks into playlist {spotify_playlist_id}...')

		playlist_insert_response = requests.post(url = playlist_url, headers = header, data = json.dumps(track_body))

		logger.info(f'status code - {playlist_insert_response.status_code}')

		if playlist_insert_response.status_code == 201:
			return True

		else:
			return False

	except Exception as err2:
		logger.error(f'failed to insert tracks into spotify playlist {spotify_playlist_id} - {err2}')
		return None

	logger.info('tracks inserted')

