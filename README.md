[contributing]: CONTRIBUTING.md
[code_of_conduct]: CODE_OF_CONDUCT.md
[license]: LICENSE

# Telescopium

Telescopium is the scraper used by [Pombo](https://pombo.di.uminho.pt/), CeSIUM's platform for LEI students at UMinho. It updates the classrooms of the classes Pombo already has, and is also used to cross-check that data.

Telescopium is not Pombo's main data source. Pombo already holds its own data, and Telescopium only complements it by confirming and updating what is there.

## How it fits in Pombo

Pombo is made of four repositories:

- [Astra](https://github.com/cesium/astra): frontend
- [Atlas](https://github.com/cesium/atlas): backend
- [Kepler](https://github.com/cesium/kepler): schedule generation
- **Telescopium**: scraper used to update and cross-check data

## 🎓 What it scrapes

Everything Telescopium scrapes comes from [alunos.uminho.pt](https://alunos.uminho.pt), UMinho's student portal.

## 🤝 Contributing

When contributing to this repository, please first discuss the change you wish
to make via discussions, issue, email, or any other method with the owners of
this repository before making a change.

Please note we have a [Code of Conduct][code_of_conduct], please follow it
in all your interactions with the project.

We have a [Contributing Guide][contributing] to help you getting started.

## 📝 License

<img src=".github/brand/cesium-DARK.svg#gh-light-mode-only" width="300">
<img src=".github/brand/cesium-LIGHT.svg#gh-dark-mode-only" width="300">

Copyright (c) 2025, CeSIUM.

This project is licensed under the MIT License - see the [LICENSE][license]
file for details.
