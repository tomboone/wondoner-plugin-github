# Wondoner GitHub Plugin

![PyPI - Version](https://img.shields.io/pypi/v/wondoner-plugin-github) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A plugin for the **Wondoner** task aggregator that enables integration with GitHub Issues.

This allows Wondoner to sync tasks based on issues within specified GitHub repositories.

## Installation

```bash
pip install wondoner-plugin-github
```

This package requires `wondoner-interfaces` to also be installed (it will be installed automatically as a dependency).

## Configuration
To use this plugin within Wondoner, you will need to provide:

1. A **GitHub Personal Access Token (PAT)** with sufficient permissions to read (and potentially write to) the repositories you want to integrate. The repo scope is typically required for private repositories.
2. The list of repositories (e.g., `owner/repo`) to monitor.

3. Configuration is typically handled within the main Wondoner application's settings or configuration files. Please refer to the main Wondoner documentation for detailed setup instructions.

## License
This project is licensed under the MIT License.