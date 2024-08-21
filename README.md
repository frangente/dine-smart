<div align="center">

# Dine-Smart

<h4>A Voice-Based Smart Assistant for Restaurant Searches and Reservations</h4>

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with pyright](https://microsoft.github.io/pyright/img/pyright_badge.svg)](https://microsoft.github.io/pyright/)

[![Python](https://img.shields.io/badge/python-3.10-blue?logo=python&logoColor=white)](https://www.python.org/)
![Rasa](https://img.shields.io/badge/Rasa-3.6-purple?style=flat&logo=Rasa&link=https%3A%2F%2Frasa.com%2F)

</div>

## Getting Started

### Installation

First, make sure that the current environment has Python 3.10 installed. Then, install the required dependencies using the following command:

```bash
pip install -r requirements.txt
```

### Usage

All the following commands must be executed in the `rasa` directory.

Currently, we do not provide trained models for the assistant, but you can train the assistant using the default configuration by running the following command:

```bash
rasa train
```

By default, in the configuration the SpellChecker and SemanticChecker components are disabled. If you need to use the assistant in a real-case scenario, where users may make spelling mistakes or input wrong venue types, you can enable these components in the `config.yml` file by simplu uncommenting the corresponding lines. If you use the SpellChecker component, you need to set the `BING_SEARCH_V7_SUBSCRIPTION_KEY` environment variable to your Bing Search v7 subscription key.

To run the action server, you need to the `GOOGLE_MAPS_API_KEY` environment variable to your Google Maps API key. This is mandatory since the assistant uses the Google Maps API to verifies the locations provided by the user and to search for venues. Optionally, you can also set the `GOOGLE_GEMINI_API_KEY` environment variable to your Google Gemini API key. This is used as a nice-to-have feature when the user inputs an out-of-scope query; if this variable is set, the assistant will inform the user that it cannot handle the request but it will also provide the response from the Google Gemini API (if not set, the assistant will simply inform the user that it cannot handle the request).

After training the assistant and setting the environment variables, you can run the assistant using the following commands:

```bash
# to run the rasa server
rasa run
# or (if you need a live shell)
rasa shell
# or (if you need an interactive shell)
rasa interactive

# to run the action server
rasa run actions
```
