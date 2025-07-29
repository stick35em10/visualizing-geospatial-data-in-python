import pandas as pd
import matplotlib.pyplot as plt
import os
import geopandas as gpd
from path import path_file, chickens_path
from helper_function import create_scatterplot

schools = pd.read_csv(path_file)  # Make sure this file exists and has Longitude/Latitude columns
chickens = pd.read_csv(chickens_path)

print(schools.columns)

## Scatterplot 1 - father heights vs. son heights with darkred square markers
# como usar um helper para plotar scatterplot
# Create a scatterplot of father and son heights with a square marker (encoded as s)
#


create_scatterplot(schools.Longitude, schools.Latitude, color='darkred', marker='s', xlabel='Longitude', ylabel='Latitude', title='School Locations', file_name=f"img/Longitude_Latitude_school_locations_s.png")
# Create_scatterplot of school locations with a pentagon marker (encoded as 'p') that is 'darkgreen'.
#plt.scatter(schools.Longitude, schools.Latitude, c='darkgreen', marker='s') #'p')

# print the first few rows of df 
print(schools.head())

# extract latitude to a new column: lat
#df['lat'] = [loc[0] for loc in df.Location]

# extract longitude to a new column: lng
#df['lng'] = [loc[1] for loc in df.Location]

# print the first few rows of df again
#print(df.head())

#plt.xlabel('Longitude')
#plt.ylabel('Latitude')
#plt.title('School Locations')
#plt.savefig("img/school_locations_s.png")  # Save the plot as a PNG image
#plt.show() # Show your plot

# Look at the first few rows of the chickens DataFrame
print(chickens.head())

# Plot the locations of all Nashville chicken permits
#plt.scatter(x = chickens.lat, y = chickens.lng)

#create_scatterplot(schools.Longitude, schools.Latitude, color='darkred', marker='s', xlabel='Longitude', ylabel='Latitude', title='School Locations', file_name=f"img/Longitude_Latitude_school_locations_s.png")
create_scatterplot(chickens.lng, chickens.lat,  color='darkred', marker='p', xlabel='Longitude', ylabel='Latitude', title='Chicken Locations', file_name=f"img/Chicken_Locations.png")

# Show the plot
#plt.show()
print(" import geopandas")
import geopandas as gpd
import matplotlib.pyplot as plt

print("world = gpd.read_file(gpd.datasets.get_path(")
# Load the world map

# Update the path to where you unzipped the shapefile
#shapefile_path = "data/ne_110m_admin_0_countries/ne_110m_admin_0_countries.shp"
shapefile_path = "data/maps/ne_110m_admin_0_countries.shp"
world = gpd.read_file(shapefile_path)
mozambique = world[world['ADMIN'] == 'Mozambique']
print("mozambique = world[world['admin'] == 'Mozambique']")
print("mozambique = world[world.admin ==")
# Plot
mozambique.plot(edgecolor='black', color='lightblue')
plt.title("Mozambique - Geometry Map")
#plt.show()

plt.savefig("img/1_Building_2_Layer_Maps/Mozambique_Geometry_Map.png")  # Save the plot as a PNG image
print("plt.savefig(")
#plt.show() # Show your plot

# https://campus.datacamp.com/courses/visualizing-geospatial-data-in-python/building-2-layer-maps-combining-polygons-and-scatterplots?ex=7
#1.2.1 Creating a GeoDataFrame & examining the geometry
# Import geopandas
#import geopandas as gpd

print(shapefile_path)

# Read in the services district shapefile and look at the first few rows.
service_district = gpd.read_file(shapefile_path)
print(service_district.head())

# Print the contents of the service districts geometry in the first row
print(service_district.loc[0, 'geometry'])

service_district.plot(edgecolor='black', color='lightblue')
#AttributeError: 'GeoDataFrame' object has no attribute 'title'
#Error: Process completed with exit code 1.
ax = service_district.plot(edgecolor='black', color='lightblue')
plt.title("Mozambique - Geometry Map")  # Defina o título
plt.savefig("img/1_Building_2_Layer_Maps/2._1_service_district_Building_2_Layer_Maps_Mozambique_Geometry_Map.png")
plt.close()  # Fecha a figura para liberar memória (opcional)


#import geopandas as gpd
#gadm41_MOZ_3.shp
#maputo = gpd.read_file("data/maps/maputo_admin.shp")
maputo = gpd.read_file("data/maps/gadm41_MOZ_3.shp")

#data/maps/ne_110m_admin_0_countries.shp
#maputo = gpd.read_file("data/maps/ne_110m_admin_0_countries.shp")
#inflating: data/maps/gadm41_MOZ_0.shp
#  inflating: data/maps/gadm41_MOZ_1.shp
# inflating: data/maps/gadm41_MOZ_2.shp
# inflating: data/maps/gadm41_MOZ_3.shp 
# Limite de Maputo

# Vias de acesso
roads = gpd.read_file("data/maps/gis_osm_roads_free_1.shp")

# Hospitais em Maputo
#hospitais = gpd.read_file("data/maps/hospitais_maputo.shp")
# gadm41_MOZ_1.shp, gadm41_MOZ_2.shp, gadm41_MOZ_3.shp, ne_110m_admin_1_states_provinces.shp
#pyogrio.errors.DataSourceError: data/maps/hospitais_maputo.shp: No such file or directory
hospitais = gpd.read_file("data/maps/gadm41_MOZ_0.shp") #gadm41_MOZ_1.shp, gadm41_MOZ_2.shp, gadm41_MOZ_3.shp, ne_110m_admin_1_states_provinces.shp, 
#inflating: data/maps/gis_osm_buildings_a_free_1.shp, inflating: data/maps/gis_osm_landuse_a_free_1.shp, data/maps/gis_osm_natural_a_free_1.shp , data/maps/gis_osm_natural_free_1.shp, 
# data/maps/gis_osm_places_a_free_1.shp, data/maps/gis_osm_places_free_1.shp, data/maps/gis_osm_pofw_a_free_1.shp , data/maps/gis_osm_pofw_free_1.shp, data/maps/gis_osm_pois_a_free_1.shp
# data/maps/gis_osm_pois_free_1.shp, data/maps/gis_osm_railways_free_1.shp, data/maps/gis_osm_roads_free_1.shp, data/maps/gis_osm_traffic_a_free_1.shp
# data/maps/gis_osm_traffic_free_1.shp, data/maps/gis_osm_transport_a_free_1.shp, data/maps/gis_osm_transport_free_1.shp , 
# data/maps/gis_osm_water_a_free_1.shp, data/maps/gis_osm_waterways_free_1.shp