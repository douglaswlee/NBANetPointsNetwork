# imports to get input data for and create underlying networks
import pandas as pd
import re
from itertools import combinations
import networkx as nx
from bs4 import BeautifulSoup, Comment
import requests

# imports for bokeh interactive vizualization
from bokeh.io import show, output_file, curdoc
from bokeh.models import Plot, Range1d, MultiLine, Circle, HoverTool, TapTool, BoxSelectTool, ColumnDataSource, LabelSet, StaticLayoutProvider, Select
from bokeh.models.widgets import Button, Div, Dropdown, RadioButtonGroup
from bokeh.models.graphs import from_networkx, NodesAndLinkedEdges, EdgesAndLinkedNodes
from bokeh.palettes import Spectral4
from bokeh.plotting import figure, reset_output
from bokeh.models.renderers import GraphRenderer, GlyphRenderer
from bokeh.layouts import layout, row, column, widgetbox
from bokeh.io import curdoc

# create (drop-down) selection widget to select a given regular season, default is 'Select Season' prompt
seasons = ['Select Season']
seasons.extend([str(yr)+'-'+str(yr+1) for yr in range(2001, 2019)])
season_select = Select(title='', value=seasons[0], options=seasons)

# create (drop-down) selection widget to select a given team for the selected regular season
# note that there are no teams initially (until a season is selected) just the 'Select Team' prompt
teams = ['Select Team']
team_select = Select(title='', value=teams[0], options=teams)

def get_soup(url):
    '''
    Parses page located at specified url into a "soup" of html content readable in python
    
    Given:
        url, string of webpage location
    Returns:
        the "soup" (python-compatible objects) of the html parsed webpage content collected and read thru
        requests
    '''
    response = requests.get(url)
    page = response.text
    return BeautifulSoup(re.sub('<!--|-->', '', page), 'html5lib')

def get_season_teams(season):
    '''
    Returns the Basketball-Reference page urls for each team that played during a specified season 
    
    Given:
        season, the (int) end year of a given NBA regular season
    Return:
        d, a dictionary of each team and the url of the team page for the given season
    '''
    
    # Parse the season page
    year = season.split('-')[1]
    szn_url = 'https://www.basketball-reference.com/leagues/NBA_' + year + '.html'
    soup = get_soup(szn_url)
    
    # Find a table listing all teams
    tbl = soup.find('table', {'id': 'team-stats-per_game'})
    
    # Fill dictionary of all team names (keys) and team pages (values) for the season
    d = {}
    rows=[row for row in tbl.find_all('tr')]
    for row in rows[:-1]:
        items = row.find_all('td')
        try:
            team = items[0].text.replace('*', '')
            d[team] = row.find('a').get('href')
        except:
            continue
    return d
    
def get_lineup_info(teampg_url, n_combo):
    '''
    For a team, gets lineup-by-lineup statistics for each individual combination of n_combo (a value in
    (2,5)) players
    
    Given:
        teampg_url, a string giving the url of the Basketball-Reference page for a team for a given season
        n_combo, an integer specifying the level of lineup combination (2, 3, 4, or 5 players)
    Return:
        df, a dataframe of the team's statistics for each possible n_combo lineup of players     
    '''
    
    # Parse the team/season's lineup page
    main_url = teampg_url + '/lineups'    
    soup = get_soup(main_url)
    
    # Find the table with all n_combo man lineups
    tbl_string = 'lineups_' + str(n_combo) + '-man_'
    tbl = soup.find('table', {'id': tbl_string})
    
    # Create dictionary whose keys are the lineup combination and values are all the statistics from the
    # table, then convert to a dataframe
    d = {}
    rows=[row for row in tbl.find_all('tr')]
    for row in rows[:-1]:
        items = row.find_all('td')
        try:
            comb = items[0].text
            d[comb] = [j.text.strip() for j in items[1:]]
        except:
            continue
    df = pd.DataFrame.from_dict(d, orient='index')
    df.columns = [k.text for k in rows[1].find_all('th')][2:]
    return df

def get_teamseason_basics(teamseason_url):
    '''
    For a team (for a given season), gets the "basics", the information located at the top of that team's
    Basketball-Reference page (example right below the "Previous Season" button: https://www.basketball
    reference.com/teams/TOR/2019.html)
    
    Given:
        teamseason_url, a string giving the url of the page for a team for a given season
    Return:
        a dictionary of the "basics" for the team for the given season (keys are name of the basic
        attribute, and values are the value of each attribute)
    '''
    
    # Parse the team/season page
    soup = get_soup(teamseason_url)
    
    # Get all content included in "basics" and convert into dict format
    pars = [p.text for p in soup.find_all('p')]
    pars = [re.split(': | \s' , b.strip().replace('\n', '')) for b in pars[2:10]]
    pars = [re.sub(r'\([^)]*\)', '', a.strip()) for b in pars for a in b if a and 'Division' not in a and 'Conference' not in a]
    pars = [re.sub(r'\,.+', '', b) for b in pars]
    return {pars[2*n]: pars[2*n+1] for n in range(int(len(pars)/2)-1)}

def convert_bbref_mp(mp):
    '''
    Converts minutes played from lineup pages (given as a string mm:ss format) into total minutes
    
    Given:
        mp, a string given the minutes played by a given lineup combination (as mm:ss)
    Returns:
        the float value of mp in total minutes 
    '''
    
    mins, secs = [int(x) for x in mp.split(':')]
    return mins + (secs/60)

def get_est_net_pts(mp, pts, pace):
    '''
    Attempts to adjust net points from lineup pages to an absolute net value, based on pace as
    number of possessions per 48 minutes and the net points as a per 100 possessions measure
    
    Given:
        mp, a float giving the number of minutes played by a team's lineup
        pts, a float giving the number of net points per 100 possessions of a team's lineup
        pace, a float giving the number of possessions per 48 minutes of the team
    Return:
        a float        
    '''
    
    mp = mp/48 # to convert pace to possession per minutes
    pts = pts/100 # points per possession
    return pace * mp * pts

def make_graph(team, season):
    '''
    Creates network graph object for a given team for a given season. Nodes of the graph object are the
    players on the team for that season. Edges reflect the time a player pair were on the court together.
    The weight of each edge is the estimated net points for this player pair (colored red if negative,
    black if positive)
    
    Given:
        team, a string for the given team name
        season, an integer for the given season
    Return:
        G, a Networkx graph as described above
    '''
    
    # get all team page urls for the given season
    teampgs = get_season_teams(season)
    
    # get the season page for the given team and get stats for all 5-man lineup combos (and convert
    # minutes played to total minutes) 
    url = 'https://www.basketball-reference.com' + teampgs[team].split('.')[0]    
    lineups_5man = get_lineup_info(url, 5)
    lineups_5man['MP2'] = lineups_5man['MP'].apply(convert_bbref_mp)
    
    # collect into a list of tuples where each tuple is a 5 player combination and its number of minutes
    # played and net points per 100 poss
    player_5man = [sorted((x[0].strip(), x[1].strip(), x[2].strip(), x[3].strip(), x[4].strip())) for x in lineups_5man.index.str.split('|')]
    wgtd_player_5man = [tuple(list(player_5man[p]) + [lineups_5man.iloc[p]['MP2']] + [float(lineups_5man.iloc[p]['PTS'])]) for p in range(len(player_5man))]
    
    # get all unique player pairs and create a dict of estimated net points for each of these pairs 
    players = set([y for x in player_5man for y in x])
    all_player_pairs = list(combinations(players, 2))
    player_pair_dict = dict.fromkeys(all_player_pairs, 0)
    
    # get the "basics" for the given team and season, particularly the pace
    teamseason_basics = get_teamseason_basics(url + '.html')
    pace = float(teamseason_basics['Pace'])
    
    # iterate through all lineup combinations and calculate the estimated net points for each player pair
    # keep only those pairs which are not zero (right now assumes cumulative net points over all lineups
    # won't add up to zero -- need to modify)
    for j in wgtd_player_5man:
        combs = list(combinations(j[:-2], 2))
        for comb in combs:
            try:
                player_pair_dict[comb] += get_est_net_pts(j[-2], j[-1], pace)
            except:
                player_pair_dict[tuple(reversed(comb))] += get_est_net_pts(j[-2], j[-1], pace)
    player_pair_dict = {k: v for k, v in player_pair_dict.items() if v != 0}
    
    # create graph object from the player pairs and their estimated net point values
    G = nx.Graph()
    G.add_weighted_edges_from([(k[0], k[1], v) for k,v in player_pair_dict.items()])
    for u,v in G.edges():
        G[u][v]['color'] = 'red' if G[u][v]['weight'] < 0 else 'black'
    return G

def get_graph_layout(graph):
    '''
    Create layout of graph object when drawn. The graph will be displayed in a circular layout (nodes
    arranged in a circle)
    
    Given:
        graph, a Networkx graph object
    Return:
        pos, a dict of tuples corresponding to the x and y positions of each node
        pos_off, a dict of tuples corresponding to the x and y positions of each node label
    '''
    
    # get intiial layout
    pos = nx.circular_layout(graph)
    
    # shift all nodes with a "non negative" x to the right, otherwise to the left
    pos_off = {}
    for k, v in pos.items():
        if v[0] >= -.000001:
            pos_off[k] = (v[0] + 0.05, v[1])
        else:
            pos_off[k] = (v[0] - 0.3, v[1])
    return pos, pos_off    

def get_graph_elems(graph):
    '''
    Convert the Networkx graph object into a graph that can be rendered by Bokeh. Creates node and edge
    renderers for the graph, labels for the nodes and interactivity for clicking on nodes (displaying just
    the node and all its linked edges). 
    '''
    
    # get all nodes
    node_ids = list(graph.nodes())
    
    # get all edges including for each edge:
    # -start and end nodes (the players in the player pair)-- kind of arbitrary since the graph is
    # undirected
    # -weight (the estimated net points for each player pair)
    # -color (red if negative, black if positive)
    start_ids = [a for a,b in graph.edges()]
    end_ids = [b for a,b in graph.edges()]
    weights = [.025*graph[a][b]['weight'] for a,b in graph.edges()]
    colors = [graph[a][b]['color'] for a,b in graph.edges()]

    # define data sources for nodes and edges
    graph_layout, label_layout = get_graph_layout(graph)
    x_graph, y_graph = [v[0] for v in graph_layout.values()], [v[1] for v in graph_layout.values()]
    x_label, y_label = [v[0] for v in label_layout.values()], [v[1] for v in label_layout.values()]
    
    
    node_ds = ColumnDataSource(data=dict(index=list(graph.nodes()),
                                         x = x_graph,
                                         y = y_graph,
                                         color=[Spectral4[0]]*len(list(graph.nodes()))),
                               name="Node Renderer")
    edge_ds = ColumnDataSource(data=dict(start= start_ids,
                                          end=end_ids,
                                          weight = weights,
                                          color = colors),
                                name="Edge Renderer")
    
    # create bokeh graph object
    # note that both nodes and edges both have specified "glyphs" for regular and selection/nonselection (as well as
    # the selection policy (NodesAndLinkedEdges())
    # when a node is selected, its outgoing edges are highlighted        
    graph_plot = GraphRenderer(node_renderer=GlyphRenderer(glyph=Circle(size=15, fill_color="color"),
                                                           selection_glyph=Circle(size=15, fill_color="color"),
                                                      data_source=node_ds),
                          edge_renderer=GlyphRenderer(glyph=MultiLine(line_alpha=0.3, line_width= 'weight', line_color = 'color'),
                                                      selection_glyph=MultiLine(line_alpha=1, line_width = 'weight', line_color = 'color'),
                                                      nonselection_glyph=MultiLine(line_alpha=0, line_width = 'weight', line_color = 'color'),
                                                      data_source=edge_ds),
                          layout_provider=StaticLayoutProvider(graph_layout=graph_layout),
                          selection_policy=NodesAndLinkedEdges())
    
    # create labels for each node as well as their positions when plotted
    label_ds = ColumnDataSource(data=dict(index=list(graph.nodes()),
                                          x = x_label,
                                          y = y_label))
    labels = LabelSet(x='x', y='y', text='index', source=label_ds,
                      background_fill_color='lightgrey')

    return graph_plot, labels  

def update_season():
    '''
    Updates the season (when user selects a season using the season_select widget), but also updates the
    list of teams for that given season. The team_select widget will still default to the 'Select Team'
    prompt
    '''
    
    # change season value to that clicked
    season = season_select.value
    
    # populate list of teams for that season as available choices to select with team_select widget
    teams = ['Select Team']
    tmpg_dict = get_season_teams(season_select.value)
    teams += sorted(list(tmpg_dict.keys()))
    team_select.value = teams[0]
    team_select.options = teams 
    
def make_plot():
    '''
    Plots the network graph for the given team for the given season (when user selects a team on the
    team_select widget, assuming a season has already been selected).
    '''
    
    # first, clear the bokeh layout of any existing plot of a network graph 
    if len(layout.children) > 1:
        layout.children.pop()
    
    # then, create a figure to plot on, create the graph and its elements to render and add to bokeh
    # layout (thus drawing the network graph)
    try:
        plot = figure(title=season_select.value + ' ' + team_select.value, tools='', x_range=(-1.6, 1.6),
          y_range=(-1.6, 1.6), toolbar_location=None, plot_width=800, plot_height=800, name='main_plot')
        plot.add_tools(HoverTool(tooltips=None), TapTool(), BoxSelectTool())
        plot.xgrid.visible=False
        plot.ygrid.visible=False
        plot.xaxis.visible=False
        plot.yaxis.visible=False
        G = make_graph(team_select.value, season_select.value)
        graph_rend, labels = get_graph_elems(G)
        plot.renderers.append(graph_rend)
        plot.renderers.append(labels)
        layout.children.append(plot)
    except:
        pass

# specify what happens when the user changes the value of each select widget
season_select.on_change('value', lambda attr, old, new: update_season())
team_select.on_change('value', lambda attr, old, new: make_plot())

# specify initial bokeh layout (when first loaded), just the season_select and team_select widgets are
# shown
dropdowns = column(season_select, team_select)
layout = row(dropdowns)
curdoc().add_root(layout)
