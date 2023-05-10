"""Support for interfacing with HDMI Matrix."""
import json
import logging
import datetime
import uuid
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
import requests



from homeassistant.components.media_player import (
    MediaPlayerEntity, 
    PLATFORM_SCHEMA
)
from homeassistant.components.media_player.const import (
    DOMAIN, 
    SUPPORT_SELECT_SOURCE
)
from homeassistant.const import (
    ATTR_ENTITY_ID, 
    CONF_HOST, 
    CONF_NAME, 
    CONF_TYPE, 
    CONF_UNIQUE_ID, 
    CONF_SCAN_INTERVAL,
    STATE_OFF,
    STATE_ON
)

_LOGGER = logging.getLogger(__name__)

SUPPORT_HDMIMATRIX = SUPPORT_SELECT_SOURCE

MEDIA_PLAYER_SCHEMA = vol.Schema({
    ATTR_ENTITY_ID: cv.comp_entity_ids,
})

ZONE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
})

SOURCE_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string,
})

CONF_ZONES = 'zones'
CONF_SOURCES = 'sources'

DATA_HDMIMATRIX = 'hdmi_matrix'

SERVICE_SETZONE = 'hdmi_matrix_set_zone'
ATTR_SOURCE = 'source'

SERVICE_SETZONE_SCHEMA = MEDIA_PLAYER_SCHEMA.extend({
    vol.Required(ATTR_SOURCE): cv.string
})

# Valid zone ids: 1-8
ZONE_IDS = vol.All(vol.Coerce(int), vol.Range(min=1, max=8))

# Valid source ids: 1-8
SOURCE_IDS = vol.All(vol.Coerce(int), vol.Range(min=1, max=8))

PLATFORM_SCHEMA = vol.All(
    cv.has_at_least_one_key(CONF_HOST),
    PLATFORM_SCHEMA.extend(
        {
            vol.Exclusive(CONF_HOST, CONF_TYPE): cv.string,
            vol.Required(CONF_ZONES): vol.Schema({ZONE_IDS: ZONE_SCHEMA}),
            vol.Required(CONF_SOURCES): vol.Schema({SOURCE_IDS: SOURCE_SCHEMA}),
    }))

def setup_platform(hass, config, add_entities, discovery_debug=None):
    """Set up the HDMI Matrix platform."""
    
    if DATA_HDMIMATRIX not in hass.data:
        hass.data[DATA_HDMIMATRIX] = {}

    host = config.get(CONF_HOST)
    connection = host

    sources = {source_id: extra[CONF_NAME] for source_id, extra
        in config[CONF_SOURCES].items()}

    devices = []
    for zone_id, extra in config[CONF_ZONES].items():
        _LOGGER.debug('Adding zone %d - %s', zone_id, extra[CONF_NAME])
        unique_id = uuid.uuid4()
        device = HDMIMatrixZone(connection, sources, zone_id, extra[CONF_NAME])
        hass.data[DATA_HDMIMATRIX][unique_id] = device
        devices.append(device)
        _LOGGER.debug('Unique ID: %s', unique_id)
        _LOGGER.debug('Device: %s', device)
    add_entities(devices, True)

    def service_handle(service):
        """Handle for services."""
        entity_ids = service.data.get(ATTR_ENTITY_ID)
        source = service.data.get(ATTR_SOURCE)
        if entity_ids:
            _LOGGER.debug('Got to entity ids')
            _LOGGER.debug(entity_ids)
            devices = [device for device in hass.data[DATA_HDMIMATRIX].values()
                        if device.entity_id in entity_ids]
        
        else:

            _LOGGER.debug('Got to entity ids else')
            devices = hass.data[DATA_HDMIMATRIX].values()

        for device in devices:
            if service.service == SERVICE_SETZONE:
                device.select_source(source)

    hass.services.register(DOMAIN, SERVICE_SETZONE, service_handle, schema=SERVICE_SETZONE_SCHEMA)


class HDMIMatrixZone(MediaPlayerEntity):
    """Representation of a HDMI matrix zone."""
    def __init__(self, hdmi_host, sources, zone_id, zone_name):
        """Initialize new zone."""
        _LOGGER.debug('Initializing New Zone')
        self._hdmi_host = hdmi_host
        # dict source_id -> source name
        self._source_id_name = sources
        # dict source name -> source_id
        self._source_name_id = {v: k for k, v in sources.items()}
        # ordered list of all source names
        self._source_names = sorted(self._source_name_id.keys(),
                                    key=lambda v: self._source_name_id[v])
        self._zone_id = zone_id
        self._name = zone_name
        self._state = 'on'
        self._source = None
        
    def update(self):
        """Retrieve latest state."""
        try:
            _LOGGER.debug('Updating...')
            updateURL = f'http://{self._hdmi_host}/AutoGetAllData'
            with requests.get(updateURL, headers={'Host': 'www.example.com'}) as response:
                _LOGGER.debug(response.content)            
                inputs = response.content
                inputs = inputs.decode().split('&')
                _LOGGER.debug(inputs)
                inputs = inputs[-11:-3]
                _LOGGER.debug(inputs)
                states = [(int(i) + 1) for i in inputs]
                state = states[self._zone_id - 1]

        except:
            self._state = STATE_OFF
            state = None
        
        if not state:
            return

        idx = state
        self._state = STATE_ON
        if idx in self._source_id_name:
            self._source = self._source_id_name[idx]
        else:
            self._source = None



    @property
    def name(self):
        """Return the name of the zone."""
        return self._name

    @property
    def state(self):
        """Return the state of the zone."""
        return self._state

    @property
    def supported_features(self):
        """Return flag of media commands that are supported."""
        return SUPPORT_HDMIMATRIX

    @property
    def media_title(self):
        """Return the current source as media title."""
        _LOGGER.debug('Media: %s', self._source)
        return self._source

    @property
    def source(self):
        """Return the current input source of the device."""
        _LOGGER.debug('Source: %s', self)
        return self._source

    @property
    def source_list(self):
        """List of available input sources."""
        return self._source_names

    def select_source(self, source):
        """Set input source."""
        if source not in self._source_name_id:
            return
        idx = self._source_name_id[source]
        _LOGGER.debug('Setting zone %d source to %s', self._zone_id, idx)

        try:
            setURL = f'http://{self._hdmi_host}/@PORT{self._zone_id}={idx}.0'
            #urllib.request.urlopen(f'http://{self._hdmi_host}/@PORT{self._zone_id}={idx}.0', timeout=5)
            requests.post(setURL, headers={'Host': 'www.example.com'})
        except:
            pass
