import os
#python/app/helper_function.py", line 13, in create_scatterplot
#    run_date = os.getenv("RUN_DATE", "local")
import matplotlib.pyplot as plt

#plt.scatter(x, y, c=color, marker=marker)
#    ^^^
#NameError: name 'plt' is not defined

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
