# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:light
#     text_representation:
#       extension: .py
#       format_name: light
#       format_version: '1.5'
#       jupytext_version: 1.10.0
#   kernelspec:
#     display_name: 'Python 3.9.1 64-bit (''des'': conda)'
#     metadata:
#       interpreter:
#         hash: a568a3391fa07a69dd36ed86d7f7005a7e6c42f5000f39f23663d14718557572
#     name: python3
# ---

# +
from os import listdir
from shutil import unpack_archive
import geopandas as gpd

from des import download
from des import io
from des import join

data_dir = "../data"
cad_data = "/home/wsl-rowanm/Data/ESBdata_20200124"
# -

# # Get LA boundaries

download.download(
    url="https://zenodo.org/record/4446778/files/dublin_admin_county_boundaries.zip",
    to_filepath=f"{data_dir}/external/dublin_admin_county_boundaries.zip"
)
unpack_archive(
    filename=f"{data_dir}/external/dublin_admin_county_boundaries.zip",
    extract_dir=f"{data_dir}/external/dublin_admin_county_boundaries",
)


dublin_admin_county_boundaries = io.read_dublin_admin_county_boundaries(
    f"{data_dir}/external/dublin_admin_county_boundaries"
)

# # Get 38kV, 110kV & 220kV stations from CAD data
#
# ... there is no 400kV station in Dublin

# Must be downloaded from the Codema Google Shared Drive or <span style="color:red">**requested from the ESB**</span>

hv_network_dirpath = f"{cad_data}/Dig Request Style/HV Data"
hv_network_filepaths = [
    f"{hv_network_dirpath}/{filename}"
    for filename in listdir(hv_network_dirpath)
]
cad_stations_ireland = io.read_network(hv_network_filepaths, levels=[20,30,40])
cad_stations_dublin = gpd.sjoin(
    cad_stations_ireland,
    dublin_admin_county_boundaries,
    op="within",
).drop(columns=["index_right", "COUNTYNAME"])

# # Get Map stations

heatmap_stations_ireland = io.read_heatmap(f"{data_dir}/external/heatmap-download-version-nov-2020.xlsx")
heatmap_stations_dublin =  gpd.sjoin(
    heatmap_stations_ireland,
    dublin_admin_county_boundaries,
    op="within",
).drop(columns="index_right")
heatmap_stations_dublin_hv = heatmap_stations_dublin.query("station_name != 'mv/lv'")

capacitymap_stations_ireland = io.read_capacitymap(f"{data_dir}/external/MapDetailsDemand.xlsx")
capacitymap_stations_dublin = gpd.sjoin(
    capacitymap_stations_ireland,
    dublin_admin_county_boundaries,
    op="within",
).drop(columns="index_right")
capacitymap_stations_dublin_hv = capacitymap_stations_dublin.query("station_name != 'mv/lv'")

# ## Link stations to nearest geocoded station

cad_stations_linked_to_heatmap = join.join_nearest_points(cad_stations_dublin, heatmap_stations_dublin_hv)

cad_stations_linked_to_capacitymap = join.join_nearest_points(cad_stations_dublin, capacitymap_stations_dublin_hv)

# # Plot CAD stations vs Heatmap stations
#
# ... Open `png` version of below plot locally (see [save](#save)) to zoom in

# +
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt

f, ax = plt.subplots(figsize=(100, 100))

dublin_admin_county_boundaries.plot(ax=ax, facecolor="teal", edgecolor="white")

cad_stations_linked_to_heatmap.plot(ax=ax, color="black")
cad_stations_linked_to_heatmap.apply(
    lambda x: ax.annotate(
        text=x["station_name"],
        xy=x.geometry.centroid.coords[0],
        ha='center',
        color="white",
        path_effects=[pe.withStroke(linewidth=2, foreground="black")],
    ),
    axis=1,
);

heatmap_stations_dublin_hv.plot(ax=ax,color="orange")
heatmap_stations_dublin_hv.apply(
    lambda x: ax.annotate(
        text=x["station_name"],
        xy=x.geometry.centroid.coords[0],
        ha='center',
        color="white",
        path_effects=[pe.withStroke(linewidth=2, foreground="orange")],
    ),
    axis=1,
);

capacitymap_stations_dublin_hv.plot(ax=ax,color="red")
capacitymap_stations_dublin_hv.apply(
    lambda x: ax.annotate(
        text=x["station_name"],
        xy=x.geometry.centroid.coords[0],
        ha='center',
        color="white",
        path_effects=[pe.withStroke(linewidth=2, foreground="red")],
    ),
    axis=1,
);

plt.legend(["CAD", "Heat Map", "Capacity Map"], prop={'size': 50});
# -

# # Save

f.savefig(f"{data_dir}/outputs/cad-stations-linked-to-nearest-heatmap-station.png")

cad_stations_linked_to_heatmap.to_file(
    f"{data_dir}/outputs/cad-stations-linked-to-nearest-heatmap-station.geojson",
    driver="GeoJSON",
)
