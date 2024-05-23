H1.I.M.E (Hydrogen-1 Imaging Made Easy) is owned by KOIOS Aerospace, please contact us at: KOIOS.Aerospace@gmail.com if you have any issues or go to KOIOSAerospace.com for more information about us.

This software would have been completely impossible without the help from Ryan Fav (Discord: ryanfav). Thank you so much!
Also, this would have been extremely hard to do without the assistance from ChatGPT v4.0 so thank you to the team at OpenAi for making such a powerful and publicly available tool!


--------HOW TO USE--------

H1.I.M.E is pretty straightforward and simple but the most important thing to mention is: 
This software is setup to use the driver "EQMOD.Telescope". It will be possible to modify the code to use your driver if necessary but otherwise you're out of luck.



-Installation-

Please run the 'Dependencies Installer.bat' file AS ADMINISTRATOR.
This will install Python as well as the other dependencies for this program.


-Notes-

The 'Position Recenter.py' file will command the mount to point at RA: 0.0 and DEC: 0.0. NOT at the center of the scan grid.

The GUI window status updates will always be 1 grid position BEHIND what is actually happening. E.g: grid position 4 slew announcement only happens AFTER its finished slewing and arrived at position 5.



-Data Acquisition-

Step 1: Power on your rig and ensure EQMOD is updated with the position of the telescope and it is correct (through checking the position with a plate-solver such as ASTAP).

Step 2: Slew the telescope to the target position of your choice through a different software (such as N.I.N.A).

Step 3: Run the 'Data Collection.py' file, this will open up and connect to your SDR as well as open a GUI.

Step 4: Input your desired grid size and spacing (if you don't know what spacing to use, use whatever FOV your dish's beam has), as well as maximum averaging time (Going over 2 seconds averaging time may induce errors).

Step 5: Press 'Select Output Folder' and choose the desired directory for where the program will store the gathered data.

Step 6: Press 'Start Scan', this will tell the mount to slew to the first grid position, record the data, then slew again to the next point...etc


-Image Generation-

After the data has been gathered, it is time to plot an image from it!

Step 1: Run the 'Image Assembler.py' file, this will open a small GUI.

Step 2: Press 'Select JSON File' and select the file that the data collection program outputted after it finished running.

After you press 'select' on file explorer, it will then generate and display the image on-screen. Save it by pressing the save icon in the bottom of the window and saving like a normal file.