import os
#python/app/helper_function.py", line 13, in create_scatterplot
#    run_date = os.getenv("RUN_DATE", "local")
import matplotlib.pyplot as plt

#plt.scatter(x, y, c=color, marker=marker)
#    ^^^
#NameError: name 'plt' is not defined

sub create_scatterplot_shapefile(shapefile_path):
    # Read in the services district shapefile and look at the first few rows.
    service_district = gpd.read_file(shapefile_path)
    print(service_district.head())

    # Print the contents of the service districts geometry in the first row
    print(service_district.loc[0, 'geometry'])

    #1.3

    service_district.plot(edgecolor='black', color='lightblue')
    #AttributeError: 'GeoDataFrame' object has no attribute 'title'
    #Error: Process completed with exit code 1.
    ax = service_district.plot(edgecolor='black', color='lightblue')
    plt.title("Mozambique - Geometry Map")  # Defina o título
    plt.savefig("img/1_Building_2_Layer_Maps/2._1_service_district_Building_2_Layer_Maps_Mozambique_Geometry_Map.png")
    plt.close()  # Fecha a figura para liberar memória (opcional)


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

    plt.savefig(file_name_)  # Save the plot as a PNG image
    print("plt.savefig saved ")
    #plt.show() # Show your plot


def create_scatterplot(x, y, color='darkred', marker='s', xlabel='X-axis', ylabel='Y-axis', title='Scatterplot', file_name=f"img/Longitude_Latitude_school_locations_s.png"):
    plt.scatter(x, y, c=color, marker=marker)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid()
    run_date = os.getenv("RUN_DATE", "local")
    run_number = os.getenv("RUN_NUMBER", "0")
    img_name = f"img/school_locations_{run_date}_run{run_number}.png"
    plt.savefig(img_name)
    #plt.show()
    #plt.savefig(file_name)  # Save the plot as a PNG image
    #filename='img/school_locations_s.png'
    #file_name = file_name if f"img/{x}_{y}_{title}_s.png" else filename
