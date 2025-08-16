import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
# from path import districts 
# Load polygon layer (districts)
# districts = gpd.read_file("data/maps/marracuene_distritos.shp")
districts = gpd.read_file("data/Service District/geo_export_ca87c034-2403-454e-8057-a3776934ed64.shp")

# data/maps/gis_osm_water_a_free_1.shp
# Load water points (CSV with longitude/latitude)
# FileNotFoundError: [Errno 2] No such file or directory: 'data/agua.csv'
#water = pd.read_csv("data/agua.csv")
"""water_gdf = gpd.GeoDataFrame(
    water,
    geometry=gpd.points_from_xy(water.longitude, water.latitude),
    crs="EPSG:4326"
)
"""
# Plot
fig, ax = plt.subplots(figsize=(10, 10))
districts.plot(ax=ax, edgecolor='black', color='lightblue', alpha=0.5)
# water_gdf.plot(ax=ax, color='blue', marker='o', label='Water Points')

plt.title("Marracuene Districts and Water Distribution")
plt.legend()
#plt.show()
plt.savefig("img/1_Building_2_Layer_Maps/1.3.3_CombiningPolygonsAndScatterplots/output.png")