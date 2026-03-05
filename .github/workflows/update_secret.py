import base64
import sys
from typing import Annotated

import requests
import typer
from nacl import encoding, public


# https://docs.github.com/en/rest/guides/encrypting-secrets-for-the-rest-api?apiVersion=2022-11-28#example-encrypting-a-secret-using-python
def encrypt(public_key: str, secret_value: str) -> str:
    """Encrypt a Unicode string using the public key."""
    public_key_ = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())  # type: ignore
    sealed_box = public.SealedBox(public_key_)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


app = typer.Typer()


@app.command()
def main(
    owner_name: str,
    repo_name: str,
    env_name: str,
    secret_name: str,
    content: str,
    gh_token: Annotated[str | None, typer.Argument(envvar="GH_TOKEN")] = None,
):
    if not gh_token:
        print("GH_TOKEN env var not set", file=sys.stderr)
        sys.exit(1)

    # Fetch public key for encoding
    api_url = f"https://api.github.com/repos/{owner_name}/{repo_name}/environments/{env_name}/secrets"
    headers = {
        "Authorization": f"Bearer {gh_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    resp = requests.get(api_url + "/public-key", headers=headers)
    resp.raise_for_status()
    # {key_id, key}
    public_key: dict = resp.json()

    encrypted_value = encrypt(public_key["key"], content)

    # Upload secret
    resp = requests.put(
        f"{api_url}/{secret_name}",
        headers=headers,
        json={"encrypted_value": encrypted_value, "key_id": public_key["key_id"]},
    )
    resp.raise_for_status()


if __name__ == "__main__":
    app()
