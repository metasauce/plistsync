# Tidal


To use Tidal, you need to have a Tidal account. To authenticate and authorize Playlist Sync to access your Tidal account, run `plistsync tidal auth` and follow the prompts.


```{typer} plistsync.services.tidal.authenticate:tidal_cli
---
prog: plistsync tidal auth
---
```


This will use the OAuth 2.0 Authorization Code Flow with PKCE to obtain an access token and refresh token, which will be saved to a file named `tidal_token.json` in the configuration directory.

Any future requests to Tidal will use the access token obtained during the authentication process. Normally you should not need to run this command again, as the refresh token will be used to obtain new access tokens automatically when needed. 


## Advanced usage

We supply a client ID for Tidal, but you can also register your own application with Tidal and use your own credentials. 


You need to create a Tidal developer account and register an application to obtain a `client_id` and `client_secret`. You can do this by visiting the [Tidal Developer Portal](https://developers.tidal.com/).
Go to your `Dashboard` and create a new application. You will need to provide a name, description, and register a redirect URI. The redirect URI should be set to `http://localhost:5001`!

:::{admonition} Port Configuration 
:class: tip

If the default port `5001` is already in use, and you do not want to use the `no-server` option, you can specify a different port by changing the `redirect_port` in your `config.yaml` file under the `tidal` section. Make sure to also update the redirect URI in your Tidal application settings to match the new port.
:::


Add the client ID, client secret, and redirect port to your `config.yaml` file under the `tidal` section:

```yaml
tidal:
    enabled: true
    client_id: YOUR_CLIENT_ID
    client_secret: YOUR_CLIENT_SECRET
    redirect_port: 5001
```

