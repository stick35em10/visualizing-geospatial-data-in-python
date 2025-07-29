import os

import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt

from path import path_file, chickens_path, shapefile_path, hospitais_path, roads_path_, maputo_path

from helper_function import create_scatterplot, print_world_info, create_scatterplot_shapefile

schools = pd.read_csv(path_file)  # Make sure this file exists and has Longitude/Latitude columns
chickens = pd.read_csv(chickens_path)

# 1.3 
maputo = gpd.read_file(maputo_path)

roads = gpd.read_file(roads_path_)

hospitais = gpd.read_file(hospitais_path)  #gadm41_MOZ_1.shp, gadm41_MOZ_2.shp, gadm41_MOZ_3.shp, ne_110m_admin_1_states_provinces.shp, 

#print(schools.columns)

## Scatterplot 1 - father heights vs. son heights with darkred square markers
# como usar um helper para plotar scatterplot
# Create a scatterplot of father and son heights with a square marker (encoded as s)

create_scatterplot(schools.Longitude, schools.Latitude, color='darkred', marker='s', xlabel='Longitude', ylabel='Latitude', title='School Locations', file_name=f"img/Longitude_Latitude_school_locations_s.png")
# Create_scatterplot of school locations with a pentagon marker (encoded as 'p') that is 'darkgreen'.
#plt.scatter(schools.Longitude, schools.Latitude, c='darkgreen', marker='s') #'p')

# print the first few rows of df 
#print(schools.head())

# extract latitude to a new column: lat
# df['lat'] = [loc[0] for loc in df.Location]

# extract longitude to a new column: lng
#df['lng'] = [loc[1] for loc in df.Location]

# print the first few rows of df again
# print(df.head())

#plt.xlabel('Longitude')
#plt.ylabel('Latitude')
#plt.title('School Locations')
#plt.savefig("img/school_locations_s.png")  # Save the plot as a PNG image
#plt.show() # Show your plot

# Look at the first few rows of the chickens DataFrame
#print(chickens.head())

# Plot the locations of all Nashville chicken permits
#plt.scatter(x = chickens.lat, y = chickens.lng)

#create_scatterplot(schools.Longitude, schools.Latitude, color='darkred', marker='s', xlabel='Longitude', ylabel='Latitude', title='School Locations', file_name=f"img/Longitude_Latitude_school_locations_s.png")
create_scatterplot(chickens.lng, chickens.lat,  color='darkred', marker='p', xlabel='Longitude', ylabel='Latitude', title='Chicken Locations', file_name=f"img/Chicken_Locations.png")

# Show the plot
#plt.show()
#print(" import geopandas")

print("world = gpd.read_file(gpd.datasets.get_path(")
# Load the world map


world = gpd.read_file(shapefile_path)


# https://campus.datacamp.com/courses/visualizing-geospatial-data-in-python/building-2-layer-maps-combining-polygons-and-scatterplots?ex=7
#1.2.1 Creating a GeoDataFrame & examining the geometry
# Import geopandas
#import geopandas as gpd

#print_world_info(world)

print(shapefile_path)

create_scatterplot_shapefile(shapefile_path)