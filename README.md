# Helios
## Electric Vehicle Solar Charge Controller

A software controller that that uses the solar energy generated by a home in excess of consumption, to charge an elecrtic vehicle.  

The current implementation supports the Enphase Solar Gateway with battery and Tesla vehicles.  The system automatically detects when a vehicle is at home, needs a charge and is plugged in.  If multiple vehicles are charge eligible, the system selects the vehicle with the lowest battery level to charge.

## Setup

### General Setup

In ```src/helios.yaml``` set how many additional watts you want to reserve for your home (```reserved_power```) to consume (above and beyond what is modeled by the controller), the min charge level of your home battery required to allow vehicle charging (```home_battery```), and update your home address information. 

```
reserved_power: 1000
home_battery: 95
home:
    street: '$YOUR_STEET_ADDRESS'
    city: '$YOUR_CITY'
    state: '$YOUR_STATE'
    postcode: '$YOUR_ZIP'
```

### Tesla Integration

In order for Helios to determine if a vehicle should be charged, it needs to know if the vehicle is at your home address, plugged in, and its charge level.  This requires access to the Tesla API. Tesla API access is also required to start charging and set the charge amperage.  You can use https://github.com/adriankumpf/tesla_auth to authenticate with Tesla and fetch access and refresh tokens. 

Once you have the tokens update the ```src/tesla_tokens.json``` file with them:

```
{ "access_token": "$YOUR_ACCCESS_TOKEN",
  "refresh_token": "$YOUR_REFRESH_TOKEN",
  "expires_in": 28800,
  "token_type": "Bearer" }
  ```

### GeoApify Integration

Helios uses GeoApify to translate the longitude and lattitude returned by the Tesla API for vehicle location into an actual address.  Follow the instructions here https://www.geoapify.com/get-started-with-maps-api in order to get an API key.  Once you have an API key update the ```src/helios.yaml``` file with your API key.

```
geoapify:
    api_url: https://api.geoapify.com/v1
    api_key: '$YOUR_GEOAPIFY_API_KEY'
```

### Enphase Integration

To monitor energy production and battery levels you need to setup an Enphase API application.  Follow the instructions here: https://developer-v4.enphase.com/docs/quickstart.html.  Helios has been optimized such that the free Watt plan should be adequate. Then populate ```src/helio.yaml``` with your Enphase System ID, API Key, Client ID, and Client Secret:

```
enphase:
    system_id: '$YOUR_ENPHASE_SYSTEM_ID'
    api_key: '$YOUR_ENPHASE_API_KEY'
    client_id: '$YOUR_ENPHASE_API_CLIENT_ID'
    client_secret: '$YOUR_ENPHASE_API_CLIENT_SECRET'
```

Now you need to authorize your enphase app to access your enphase system.  Simply run:

```cd src && ./helios -e```

This will return an authorization url that will allow you to log into your Enphase account and fetch an authorization code.  Once you have an authorization code, update ```src/helios.yaml``` with your code:

```
enphase:
    auth_code: '$YOUR_ENPHASE_AUTH_CODE'
```

### Running Helios

```cd src && ./helios```

Depending on the time of day you should see something like this:

```
2022-09-10 19:52:52,081 INFO 223:evscc(1) - Starting the EV Solar Charge Controller ...
2022-09-10 19:52:52,081 INFO 224:evscc(1) - Processing configuration: evscc.yaml ...
2022-09-10 19:52:55,583 INFO 79:evscc(1) - Found timezone of America/Los_Angeles.
2022-09-10 19:52:57,088 INFO 94:evscc(1) - Found generation range of 8:00 to 18:00.
2022-09-10 19:52:57,435 INFO 302:tesla.py(1) - Found vehicle named Marty [XXXXXXXXXXXXXXXX].
2022-09-10 19:52:58,113 INFO 302:tesla.py(1) - Found vehicle named Stella [XXXXXXXXXXXXXXXX].
2022-09-10 19:53:23,049 INFO 327:tesla.py(1) - Selected Stella [XXXXXXXXXXXXXXXX] @ 79% charge level.
2022-09-10 19:53:23,049 INFO 122:evscc(1) - Initial charging amps set to: 48.
2022-09-10 19:53:23,049 INFO 123:evscc(1) - Entering control loop ...
2022-09-10 19:53:23,049 INFO 126:evscc(1) - Checking to see if anything needs to be adjusted ...
2022-09-10 19:53:28,643 INFO 174:evscc(1) - Vehicle connected at home and solar power is being generated.
2022-09-10 19:53:30,203 INFO 81:control.py(1) - Found a power target of 4491 watts.
2022-09-10 19:53:30,203 INFO 88:control.py(1) - Found an amperage target of 18.
2022-09-10 19:53:30,301 INFO 177:tesla.py(1) - Setting charging amps to 18.
2022-09-10 19:53:30,660 INFO 185:tesla.py(1) - Starting to charge.
```

It's recommended you build a docker container and deploy the service to Amazon ECS.
