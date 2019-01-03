# NBANetPointsNetwork

This repo contains the notebook `NBA_NetPts_Network.ipynb` which performs the following:

1. Scrapes lineup-level data from Basketball-Reference ([example](https://www.basketball-reference.com/teams/TOR/2019/lineups/#all_lineups_5-man_)) for a given team for a given season (team season).
2. From the lineup-level data, calculates the estimated net points for each pair of players with a record in the table. This estimate uses the given team season's Pace (possessions per 48 mins) and a sum of the products of the player pair's total minutes played and net points per 100 possessions in each 5-man lineup in which the pair appeared.
3. Creates an undirected network graph, using `NetworkX` based on this estimated player pair net point data, where:
* Each node corresponds to each individual player for the team season
* Each edge reflects that a pair of players shared the court for a given minimum threshold of minutes. The weight of each edge corresponds to the estimate net points contributed by a player pair. The color indicates if the estimated net points of the pair are negative (red) or positive (black)
