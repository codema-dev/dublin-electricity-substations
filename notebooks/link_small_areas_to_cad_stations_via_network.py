# -*- coding: utf-8 -*-
# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:light
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.9.1
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# +
import pickle

import geopandas as gpd
import matplotlib.pyplot as plt
import momepy
import networkx as nx
import pandas as pd
from tqdm import tqdm

from des.distance import get_nearest_node
from des.distance import get_nearest_nodes
from des.distance import get_network_paths_between_points
from des.distance import get_network_paths_between_points_lazy
from des.plot import plot_gdf_vs_nx
from des.plot import plot_path_n
from des.plot import plot_paths_to_files
# -

# # Get Small Area boundaries

# +
# --no-clobber skips downloading unless a new version exists
# !wget --no-clobber \
#     -O ../data/external/Small_Areas_Ungeneralised_-_OSi_National_Statistical_Boundaries_-_2015-shp.zip \
#     https://opendata.arcgis.com/datasets/c85e610da1464178a2cd84a88020c8e2_3.zip

# -o forces overwriting
# !unzip -o \
#     -d ../data/external/Small_Areas_Ungeneralised_-_OSi_National_Statistical_Boundaries_-_2015-shp \
#     ../data/external/Small_Areas_Ungeneralised_-_OSi_National_Statistical_Boundaries_-_2015-shp.zip 
# -

small_areas = (
    gpd.read_file("../data/external/Small_Areas_Ungeneralised_-_OSi_National_Statistical_Boundaries_-_2015-shp")
    .query("`COUNTYNAME` == ['South Dublin', 'Dún Laoghaire-Rathdown', 'Fingal', 'Dublin City']")
    .loc[:, ["SMALL_AREA", "COUNTYNAME", "geometry"]]
    .to_crs(epsg=2157) # convert to ITM
)

# # Get Local Authority boundaries

# +
# --no-clobber skips downloading unless a new version exists
# !wget --no-clobber \
#     -O ../data/external/dublin_admin_county_boundaries.zip \
#     https://zenodo.org/record/4446778/files/dublin_admin_county_boundaries.zip

# -o forces overwriting
# !unzip -o \
#     -d ../data/external \
#     ../data/external/dublin_admin_county_boundaries.zip 
# -

dublin_admin_county_boundaries = (
    gpd.read_file("../data/external/dublin_admin_county_boundaries")
    .to_crs(epsg=2157) # read & convert to ITM or epsg=2157
)

# # Get Network data

# Must be downloaded from the Codema Google Shared Drive or <span style="color:red">**requested from the ESB**</span>

network_data = "/home/wsl-rowanm/Data/dublin-electricity-network/"

# ## Get MV Network

lv_network = (
    gpd.read_parquet(f"{network_data}/dublin_lvmv_network.parquet")
    .query("`voltage_kv` == 'lv'")
    .copy()
)

lv_network_lines = (
    lv_network.query("`Level` == [1, 2, 5]")
    .explode()
    .reset_index()
    .drop(columns="level_1")
    .loc[:, ["geometry"]]
    .copy()
)

mv_network = (
    gpd.read_parquet(f"{network_data}/dublin_lvmv_network.parquet")
    .query("`voltage_kv` == 'mv'")
    .copy()
)

mv_network_lines = (
    mv_network.query("`Level` == [10, 11, 14]")
    .explode()
    .reset_index()
    .drop(columns="level_1")
    .loc[:, ["geometry"]]
    .copy()
)

# ## Get 38kV, 110kV & 220kV  stations
#
# ... there is no 400kV station in Dublin

hv_network = (
    gpd.read_parquet(f"{network_data}/dublin_hv_network.parquet")
    .to_crs(epsg=2157)
    .reset_index()
    .loc[: , ["Level", "voltage_kv", "geometry"]]
)

hv_lines_38kv = hv_network.query("`Level` == [21, 24]").dissolve(by="voltage_kv")
hv_lines_110kv = hv_network.query("`Level` == [31, 34]").dissolve(by="voltage_kv")
hv_lines_220kv = hv_network.query("`Level` == [41, 44]").dissolve(by="voltage_kv")

hv_stations = (
    hv_network.query("`Level` == [20, 30, 40]")
    .copy()
    .explode() # un-dissolve station locations from multipoint to single points
    .reset_index()
    .drop(columns="level_1")
)

hv_stations_38kv = hv_stations.query("`Level` == 20")
hv_stations_110kv = hv_stations.query("`Level` == 30")
hv_stations_220kv = hv_stations.query("`Level` == 40")

# # Link Each Small Area Centroid to a Station via Network
#
# Use `networkx` to find the station that is closest along the network to each small area centroid:
# - Convert `geopandas` `GeoDataFrame` to `networkx` `MultiGraph` via `momepy`
# - Link each small area centroid and station to the nearest corresponding node in the network
# - Find the nearest station to each centroid

# ## Convert to NetworkX
#
#

G = momepy.gdf_to_nx(mv_network_lines, approach="primal")

plot_gdf_vs_nx(
    G=G,
    gdf=mv_network_lines,
    boundaries=dublin_admin_county_boundaries.boundary
)

# Filter out all of the tiny sub-networks

largest_components = [
    component for component in sorted(nx.connected_components(G), key=len, reverse=True)
    if len(component) > 5
]

G_top = nx.compose_all(G.subgraph(component) for component in tqdm(largest_components))

with open('../data/interim/G_top.pkl', 'wb') as fp:
    pickle.dump(G_top, fp)

plot_gdf_vs_nx(
    G=G_top,
    gdf=mv_network_lines,
    boundaries=dublin_admin_county_boundaries.boundary
)

# ## Link SA centroids to nearest station on MV network

orig_points = pd.DataFrame(
    {
        "x": small_areas.geometry.centroid.x,
        "y": small_areas.geometry.centroid.y,
    }
)

dest_points = pd.DataFrame(
    {
        "x": hv_stations_38kv.geometry.x,
        "y": hv_stations_38kv.geometry.y,
    }
)

paths = get_network_paths_between_points(
    G=G_top,
    orig_points=orig_points,
    dest_points=dest_points,
)

with open('../data/interim/paths.pkl', 'wb') as fp:
    pickle.dump(paths, fp)

# ## Plot shortest paths

plot_path_n(
    G=G_top,
    paths=paths,
    orig_points=orig_points,
    dest_points=dest_points,
    boundaries=dublin_admin_county_boundaries.boundary,
    n=3,
)

plot_paths_to_files(
    G=G_top,
    paths=paths,
    orig_points=orig_points,
    dest_points=dest_points,
    boundaries=dublin_admin_county_boundaries.boundary,
    dirpath="../data/outputs/sa-centroids-to-38kv-stations-via-mv-network",
)