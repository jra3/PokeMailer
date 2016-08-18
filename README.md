# Pokemon Email Alerts

A webhook powered notifier for use with [https://github.com/PokemonGoMap/PokemonGo-Map.git]


## Setup

```
pip install -r requirements.txt

cp config.json.example config.json
cp wanted.json.example wanted.json
```

Now fill out those json files...

When using PokemonGo-Map, use the option `-wh 'http://localhost:5000/pokemon'`