# Tidal

To use Tidal, you need to create a Tidal developer account and register an application to obtain a `client_id` and `client_secret`. You can do this by visiting the [Tidal Developer Portal](https://developers.tidal.com/).


Go to you `Dashboard` and create a new application. You will need to provide a name, description, and register a redirect URI. The redirect URI should be set to `http://localhost:5001`!


:::{admonition} Port Configuration 
:class: tip

If the default port `5001` is already in use, you can change it in the configuration file.
:::


Add the client ID, client secret, and redirect port to your `config.yaml` file under the `tidal` section:

```yaml
tidal:
    enabled: true
    client_id: YOUR_CLIENT_ID
    client_secret: YOUR_CLIENT_SECRET
    redirect_port: 5001
```

To complete the setup, you need to authenticate your application with Tidal. You can do this by running the following command:

```{typer} plistsync.services.tidal.authenticate:tidal_cli
---
prog: plistsync tidal auth
---
```

Any future requests to Tidal will use the access token obtained during the authentication process. Normally you should not need to run this command again, as the refresh token will be used to obtain new access tokens automatically when needed. 
