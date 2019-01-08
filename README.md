# NBANetPointsNetwork

This repo contains the notebook `NBA_NetPts_Network.ipynb` which performs the following:

1. Scrapes lineup-level data from Basketball-Reference ([example](https://www.basketball-reference.com/teams/TOR/2019/lineups/#all_lineups_5-man_)) for a given team for a given season (team season).
2. From the lineup-level data, calculates the estimated net points for each pair of players with a record in the table. This estimate uses the given team season's Pace (possessions per 48 mins) and a sum of the products of the player pair's total minutes played and net points per 100 possessions in each 5-man lineup in which the pair appeared.
3. Creates an undirected network graph, using `NetworkX` based on this estimated player pair net point data, where:
* Each node corresponds to each individual player for the team season
* Each edge reflects that a pair of players shared the court for a given minimum threshold of minutes. The weight of each edge corresponds to the estimate net points contributed by a player pair. The color indicates if the estimated net points of the pair are negative (red) or positive (black)

There are limitations to these network representations -- first the data from Basketball-Reference is not complete as there is a minutes threshold (I believe it is 30 minutes minimum) in the 5-man lineup data, so that the numbers produced from the above do not reflect the true *Net Points Contributed* by each player pair. This calculation also presents other limitations, for example, rather than use a constant Pace for all lineups, even an average Pace for each individual lineup might lead to a better estimate of *Net Points Contributed* for each player pair. Digging even further into play-by-play data would allow for characterization of net points for given lineups and player pairs down to each possession, each opposing lineup, as well as playing at home or not. Using estimates of individual player contributions based on this level of data, such as [Regularized Adjusted](https://squared2020.com/2017/09/18/deep-dive-on-regularized-adjusted-plus-minus-i-introductory-example/) [Plus-Minus](https://squared2020.com/2017/09/18/deep-dive-on-regularized-adjusted-plus-minus-ii-basic-application-to-2017-nba-data-with-r/) (RAPM). Furthermore, considering usage patterns while each lineup is on the court might also add insight, given potential [impacts of usage on team efficiency](http://www.sloansportsconference.com/mit_news/putting-the-team-on-their-back-the-usage-and-efficiency-of-nba-superstars-in-critical-situations/) (scoring and scoring prevention per possession). Additionally, other factors such as the state of the game impact  as there are clear differences. However from the examples in the notebook included here, these network representations do provide a reasonable vehicle for simple, "quick and dirty" insights about these teams.
