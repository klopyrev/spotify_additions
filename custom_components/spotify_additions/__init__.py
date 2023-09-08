import json
import logging
import voluptuous as vol

from homeassistant.components.spotify import HomeAssistantSpotifyData
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation
from homeassistant.helpers.typing import ConfigType

DOMAIN = "spotify_additions"

PLAYLIST_NAME = "Home Assistant Song Radio"

log = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({}, extra=vol.ALLOW_EXTRA)


def get_current_track_id(data: HomeAssistantSpotifyData) -> str | None:
    current_track = data.client.current_user_playing_track()
    if current_track is None:
        return None
    return current_track["item"]["id"]


def delete_existing_playlist(data: HomeAssistantSpotifyData):
    offset = 0
    limit = 50
    playlists = []
    while True:
        next_playlists = data.client.user_playlists(
            data.current_user["id"], offset=offset, limit=limit
        )
        playlists.extend(next_playlists["items"])

        offset += limit
        if offset >= next_playlists["total"]:
            break

    playlist_id_to_delete = None
    for playlist in playlists:
        if playlist["name"] == PLAYLIST_NAME:
            playlist_id_to_delete = playlist["id"]

    if playlist_id_to_delete is not None:
        data.client.current_user_unfollow_playlist(playlist_id_to_delete)


def get_recommended_track_ids(data: HomeAssistantSpotifyData, seed_track_id: str):
    recommendations = data.client.recommendations(
        seed_tracks=[seed_track_id],
        limit=100,
    )

    track_ids = []
    for track in recommendations["tracks"]:
        track_ids.append(track["id"])

    return track_ids


def create_new_playlist(data: HomeAssistantSpotifyData, track_ids: list[str]):
    playlist = data.client.user_playlist_create(
        data.current_user["id"],
        "Home Assistant Song Radio",
        public=False,
    )
    uri = playlist["uri"]

    data.client.playlist_replace_items(uri, track_ids)

    return uri


def start_playback(data: HomeAssistantSpotifyData, uri: str):
    data.client.start_playback(context_uri=uri)


def handle_create_song_radio(call: ServiceCall, data: HomeAssistantSpotifyData):
    current_track_id = get_current_track_id(data)
    if current_track_id is None:
        return

    delete_existing_playlist(data)

    recommended_track_ids = get_recommended_track_ids(data, current_track_id)

    playlist_uri = create_new_playlist(data, recommended_track_ids)

    start_playback(data, playlist_uri)


def handle_favorite_song(call: ServiceCall, data: HomeAssistantSpotifyData):
    current_track_id = get_current_track_id(data)
    if current_track_id is None:
        return

    if data.client.current_user_saved_tracks_contains([current_track_id])[0]:
        return

    data.client.current_user_saved_tracks_add([current_track_id])


def setup(hass: HomeAssistant, config: ConfigType) -> bool:
    data = None
    for d in hass.data["spotify"].values():
        data = d
    assert data is not None

    hass.services.register(
        DOMAIN,
        "create_song_radio",
        lambda call: handle_create_song_radio(call, data),
    )
    hass.services.register(
        DOMAIN,
        "favorite_song",
        lambda call: handle_favorite_song(call, data),
    )

    return True
