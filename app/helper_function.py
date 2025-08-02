import os
#python/app/helper_function.py", line 13, in create_scatterplot
#    run_date = os.getenv("RUN_DATE", "local")
import matplotlib.pyplot as plt

import geopandas as gpd
import pandas as pd

#plt.scatter(x, y, c=color, marker=marker)
#    ^^^
#NameError: name 'plt' is not defined
from path import shapefile_path, chickens, service_district  #, hospitais_path, roads_path_, maputo_path



#service_district = gpd.read_file(shapefile_path)
# Carregar pontos de distribuição de água
# agua = pd.read_csv("data/agua.csv")

#def Plot_the_service_district_shapefile(shapefile_path, chickens_path, title_="Mozambique - Geometry Map", file_name_="img/1.3.2_Plotting_points_over_polygons__part_1/1.3.1_service_district_Building_2_Layer_Maps_Mozambique_Geometry_Map.png"):   
def Plot_the_Marracuene_service_district_shapefile(marracuene, title_="distritos de Marracuene", file_name_="img/1_Building_2_Layer_Maps/1.3.1_service_district_Marracuene_Building_2_Layer_Maps_Mozambique_Geometry_Map.png"):
    agua = pd.read_json("data/Marracune/export.geojson") #pd.read_csv("data/agua.csv")
    agua_gdf = gpd.GeoDataFrame(
        agua,
        geometry=gpd.points_from_xy(agua.longitude, agua.latitude),
        crs="EPSG:4326"
    )

    # Plotar
    fig, ax = plt.subplots(figsize=(10, 10))
    marracuene.plot(ax=ax, edgecolor='black', color='lightblue', alpha=0.5)
    agua_gdf.plot(ax=ax, color='blue', marker='o', label='Distribuição de Água')

    # plt.title("Distritos de Marracuene e Distribuição da Água")
    plt.title(title_)  # Defina o título
    plt.legend()
    plt.savefig(file_name_)
    plt.close()
    #plt.show()


#def Plot_the_service_district_shapefile(shapefile_path, chickens_path, title_="Mozambique - Geometry Map", file_name_="img/1_Building_2_Layer_Maps/1.3.1_service_district_Building_2_Layer_Maps_Mozambique_Geometry_Map.png"):

def Plotting_points_over_polygons__part_2(service_district, title_="Plotting_points_over_polygons__part_2", file_name_="img/1.3.3_Plotting_points_over_polygons__part_2/1.3.3Plotting_points_over_polygons__part_2.png"):
        # Plot the service district shapefile
    service_district.head()  # Look at the first few rows of the service district GeoDataFrame
    print(service_district.head())
    # KeyError: 'name'
    #service_district.plot(column="name")
    
    #maputo_path
    #ImportError: cannot import name 'maputo_' from 'path' (/home/runner/work/visualizing-geospatial-data-in-python/visualizing-geospatial-data-in-python/app/path.py)
    
    #maputo_.plot(edgecolor='black', color='lightblue')
    
    #service_district.head()
    #maputo_.head()
    # Add the chicken locations
    
    plt.scatter(x=chickens.lng, y=chickens.lat, c = 'black')

    # Show the plot
    #plt.show()
    plt.title(title_)  # Defina o título
    plt.savefig(file_name_)
    plt.close()  # Fecha a figura para liberar memória (opcional)

    #service_district.head()

    # Plot the service district shapefile
    service_district.plot(column="name", legend=True)

    #plt.show()
    # Add the chicken locations
    #plt.scatter(x=____, y=____, c=____, edgecolor = 'white')


    # Add labels and title
    #plt.____('Nashville Chicken Permits')
    #plt.xlabel(____)
    #plt.ylabel(____)

    # Add grid lines and show the plot
    #plt.____()
    #plt.____()

def Plot_the_service_district_shapefile(shapefile_path, chickens_path, title_="Mozambique - Geometry Map", file_name_="img/1.3.2_Plotting_points_over_polygons__part_1/1.3.1_service_district_Building_2_Layer_Maps_Mozambique_Geometry_Map.png"):
    #service_district = gpd.read_file(shapefile_path)
    # Plot the service district shapefile
    #service_district.head()  # Look at the first few rows of the service district GeoDataFrame
    print(" in line 65 and inside Plot_the_service_district_shapefile", service_district.head())
    # KeyError: 'name'
    #service_district.plot(column="name")
    
    #maputo_path
    #ImportError: cannot import name 'maputo_' from 'path' (/home/runner/work/visualizing-geospatial-data-in-python/visualizing-geospatial-data-in-python/app/path.py)
    
    #maputo_.plot(edgecolor='black', color='lightblue')
    
    #service_district.head()
    #maputo_.head()
    # Add the chicken locations
    
    plt.scatter(x=chickens.lng, y=chickens.lat, c = 'black')

    # Show the plot
    #plt.show()
    plt.title(title_)  # Defina o título
    plt.savefig(file_name_)
    plt.close()  # Fecha a figura para liberar memória (opcional)



def create_scatterplot_shapefile(service_district, title_="Mozambique - Geometry Map", file_name_="img/1_Building_2_Layer_Maps/2._1_service_district_Building_2_Layer_Maps_Mozambique_Geometry_Map.png" ):

#def create_scatterplot_shapefile(shapefile_path, title_="Mozambique - Geometry Map", file_name_="img/1_Building_2_Layer_Maps/2._1_service_district_Building_2_Layer_Maps_Mozambique_Geometry_Map.png" ):
#def create_scatterplot_shapefile(service_district, title_="Mozambique - Geometry Map", file_name_="img/1_Building_2_Layer_Maps/2._1_service_district_Building_2_Layer_Maps_Mozambique_Geometry_Map.png" ):

    # Read in the services district shapefile and look at the first few rows.
    #service_district = gpd.read_file(shapefile_path)
    print(service_district.head())

    # Print the contents of the service districts geometry in the first row
    print(service_district.loc[0, 'geometry'])

    #1.3

    service_district.plot(edgecolor='black', color='lightblue')
    #AttributeError: 'GeoDataFrame' object has no attribute 'title'
    #Error: Process completed with exit code 1.
    ax = service_district.plot(edgecolor='black', color='lightblue')
    plt.title(title_)  # Defina o título
    plt.savefig(file_name_)
    plt.close()  # Fecha a figura para liberar memória (opcional)

# print_world_info(world, moz='Mozambique', title_="Mozambique - Geometry Map", file_name_="img/1_Building_2_Layer_Maps/2._1_world_Building_2_Layer_Maps_Mozambique_Geometry_Map.png")
#                     ^^^^^
# NameError: name 'world' is not defined

#world = gpd.read_file(shapefile_path)
def print_world_info(world, moz='Mozambique', title_="Mozambique - Geometry Map", file_name_="img/1_Building_2_Layer_Maps/2._1_world_Building_2_Layer_Maps_Mozambique_Geometry_Map.png"):
    
    print(world.head())  # Print the first few rows of the world GeoDataFrame
    print(world.columns)  # Print the columns of the world GeoDataFrame 
    
    mozambique = world[world['ADMIN'] == moz]
    #print("mozambique = world[world['admin'] == 'Mozambique']")
    #print("mozambique = world[world.admin ==")
    # Plot
    mozambique.plot(edgecolor='black', color='lightblue')
    plt.title(title_)
    #plt.show()
    
    run_date = os.getenv("RUN_DATE", "local")
    run_number = os.getenv("RUN_NUMBER", "0")
    img_name = f"img/1_Building_2_Layer_Maps/world_{moz}_{run_date}_run{run_number}.png"
    plt.savefig(img_name)

    #plt.savefig(file_name_)  # Save the plot as a PNG image
    print("plt.savefig saved ")
    #plt.show() # Show your plot


def create_scatterplot(x, y, color='darkred', marker='s', xlabel='X-axis', ylabel='Y-axis', title='Scatterplot'):#, file_name=f"img/Longitude_Latitude_school_locations_s.png"):
    
    plt.scatter(x, y, c=color, marker=marker)
    
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid()
    
    run_date = os.getenv("RUN_DATE", "local")
    run_number = os.getenv("RUN_NUMBER", "0")
    
    img_name = f"img/1_Building_2_Layer_Maps/1.Introduction/school_locations_{run_date}_run{run_number}.png"
    #file_name = file_name if f"img/{x}_{y}_{title}_s.png" else img_name
    
    plt.savefig(img_name)
    #plt.show()
    #plt.savefig(file_name)  # Save the plot as a PNG image
    #filename='img/school_locations_s.png'
    #file_name = file_name if f"img/{x}_{y}_{title}_s.png" else filename
