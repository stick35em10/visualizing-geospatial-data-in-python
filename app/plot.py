import os
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
from path import schools, chickens, world,  shapefile_path # , roads, hospitais, maputo, roads,  path_file, chickens_path, hospitais_path, roads_path_, maputo_, pathmaputo_,
from helper_function import Plot_the_service_district_shapefile, create_scatterplot, print_world_info # , create_scatterplot_shapefile

#1.3.1 # Plot the service district shapefile
Plot_the_service_district_shapefile(shapefile_path, chickens, title_="Mozambique - Geometry Map", file_name_="img/1_Building_2_Layer_Maps/1.3.1_service_district_Building_2_Layer_Maps_Mozambique_Geometry_Map.png")

#1.3.2                                    
print_world_info(world, moz='Mozambique', title_="Mozambique - Geometry Map", file_name_="img/1_Building_2_Layer_Maps/2._1_world_Building_2_Layer_Maps_Mozambique_Geometry_Map.png")

## Scatterplot 1 - father heights vs. son heights with darkred square markers# como usar um helper para plotar scatterplot
# Create a scatterplot of father and son heights with a square marker (encoded as s)
create_scatterplot(schools.Longitude, schools.Latitude, color='darkred', marker='s', xlabel='Longitude', ylabel='Latitude', title='School Locations') #, file_name=f"img/Longitude_Latitude_school_locations_s.png")
# Create_scatterplot of school locations with a pentagon marker (encoded as 'p') that is 'darkgreen'.
#plt.scatter(schools.Longitude, schools.Latitude, c='darkgreen', marker='s') #'p')

#create_scatterplot(schools.Longitude, schools.Latitude, color='darkred', marker='s', xlabel='Longitude', ylabel='Latitude', title='School Locations', file_name=f"img/Longitude_Latitude_school_locations_s.png")
create_scatterplot(chickens.lng, chickens.lat,  color='darkred', marker='p', xlabel='Longitude', ylabel='Latitude', title='Chicken Locations') #, file_name=f"img/Chicken_Locations.png")

# https://campus.datacamp.com/courses/visualizing-geospatial-data-in-python/building-2-layer-maps-combining-polygons-and-scatterplots?ex=7
#1.2.1 Creating a GeoDataFrame & examining the geometry
# Import geopandas

# def create_scatterplot_shapefile(service_district, title_="Mozambique - Geometry Map", file_name_="img/1_Building_2_Layer_Maps/2._1_service_district_Building_2_Layer_Maps_Mozambique_Geometry_Map.png" ):
# create_scatterplot_shapefile(service_district, title_="Mozambique - Geometry Map", file_name_="img/1_Building_2_Layer_Maps/2._1_service_district_Building_2_Layer_Maps_Mozambique_Geometry_Map.png" )