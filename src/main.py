import credentials
import api_operations
import logging
import base64
import os
from datetime import date

def main():

	root_path = os.path.dirname(os.path.dirname(__file__))

	logger = logging.getLogger(__name__)
	logging.basicConfig(
		filename = f'{root_path}/log/chunes_agg_discord_bot.log'
		,filemode = 'w'
		,format = '%(asctime)s -- %(message)s'
		,encoding = 'utf-8'
		,level = logging.INFO
	)

	logger.info('bot now botting !')

	## config
	discord_base = 'https://discord.com/api'
	discord_guild_id = '1083905997942296586' ## fam bidness
	discord_channel = 'chunes'

	spotify_auth_base = 'https://accounts.spotify.com'
	spotify_web_base = 'https://api.spotify.com/v1'
	spotify_refresh_token_3leg = credentials.spotify_refresh_token_3leg
	spotify_client_id = credentials.spotify_client_id
	spotify_client_secret = credentials.spotify_client_secret
	spotify_playlist_id = '60tHhs9aeSr92VYqoq52EW' ## chunes_test_playlist

	logger.info('config complete')

	## set up api headers
	discord_header = {'Authorization': f'Bot {credentials.discord_bot_token}'}

	spotify_client_creds_encoded = base64.b64encode((spotify_client_id + ":" + spotify_client_secret).encode("ascii")).decode("ascii")

	keep_going = True

	logger.info('api headers set up')

	# target_day = date(2024, 9, 16)

	## begin flow

	logger.info('refreshing spotify access token...')
	spotify_refreshed_access_token = api_operations.get_spotify_access_token_refresh(logger, spotify_auth_base, spotify_refresh_token_3leg, spotify_client_creds_encoded)
	
	if spotify_refreshed_access_token != None:
		keep_going = True
		logger.info('spotify access token refreshed')

	else:
		keep_going = False
		logger.error('failed to refresh spotify access token - bot is exiting (repairs needed)...')

	logger.info('beginning ingest flow')
	logger.info('getting discord_channel_id...')
	discord_channel_id = api_operations.get_guild_channels(logger, discord_base, discord_guild_id, discord_header, target_channel = discord_channel)
	logger.info(f'discord_channel_id for discord_channel {discord_channel} --> {discord_channel_id}')

	logger.info('getting spotify_target_tracks from discord channel...')
	if discord_channel_id != None:
		spotify_target_tracks = api_operations.get_guild_channel_messages(logger, discord_base, discord_header, discord_channel_id, target_day = None)
		keep_going = True
		logger.info('spotify objects collected --> \n' + '\n'.join(spotify_target_tracks))
	else:
		keep_going = False
		logger.error('failed to collect spotify_target_tracks from discord channel  - bot is exiting (repairs needed)...')

	if spotify_target_tracks != None:
		logger.info('beginning track cleanup')
		scrubbed_track_list = api_operations.spotify_track_cleanup(logger, spotify_web_base, spotify_refreshed_access_token, spotify_target_tracks)
		keep_going = True

	elif len(spotify_target_tracks) > 0 and spotify_target_tracks[0] != 200:
		keep_going = False
		logger.error('api call failed - bot is exiting... (repairs needed)')

	else:
		keep_going = False
		logger.error('no tracks found today - bot is exiting...')

	logger.info(f'beginning spotify_target_tracks upsert into spotify_playlist_id {spotify_playlist_id}')
	if scrubbed_track_list != None and keep_going == True:
		insert_success = api_operations.upsert_spotify_track_into_playlist(logger, spotify_web_base, spotify_refreshed_access_token, scrubbed_track_list, spotify_playlist_id)
		keep_going = True

	else:
		keep_going = False

	if insert_success == True and keep_going == True:
		logger.info('tracks from today successfully upserted.. good shit !')
	else:
		logger.error('tracks from today failed to upserted.. figure it out bruh !')

if __name__ == '__main__':
	main()