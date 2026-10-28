[uv]: https://docs.astral.sh/uv/

# 🚀 Getting Started

These instructions will get you a copy of the project up and running on your
local machine for development and testing purposes.

## 📥 Prerequisites

The following software is required to be installed on your system:

- [uv][uv]

You don't need to install Python yourself: the project requires Python 3.13+
and `uv` will download and manage the right version for you.

## 🔧 Setup

First, clone the repository:

```
git clone git@github.com:cesium/telescopium.git
cd telescopium
```

Then, install all the dependencies. This creates a virtual environment and
installs everything the project needs.

```
uv sync
```

If you want to export the data as `.ics` calendar files, also install the
optional `ics` dependencies.

```
uv sync --extra ics
```

## ⚙️ Configuration

Telescopium needs a configuration to know what to scrape. How you provide it
depends on how you run the project (see below):

- When using `solve`, the configuration is read from the `config.yml` file at
  the root of the repository, so you need to set it up before running.
- When using the API, you can pass the configuration directly on each request,
  so no `config.yml` is needed.

## 🔨 Development

Telescopium can be run in two different ways.

### Export to a file

Run the scraper once and export the collected data to the output file. This
uses the configuration in `config.yml`.

```
uv run main.py solve
```

### API

Start the API and then you can send requests to it. The example below makes it
available at `http://localhost:5000`.

```
uv run main.py api 0.0.0.0 5000
```

The first argument is the host and the second is the port.

### Formatting

This project uses [Black](https://black.readthedocs.io/) to keep the code
consistently formatted. Format your code before opening a pull request.

```
uv run black .
```

### Dependencies

Add a new dependency.

```
uv add <package>
```

Remove a dependency.

```
uv remove <package>
```

Don't forget to commit the updated `pyproject.toml` and `uv.lock`.
