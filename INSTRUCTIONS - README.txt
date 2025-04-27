Welcome to H1IME, which stands for Hydrogen 1 Imaging Made Easy! This program uses an ASCOM motorized telescope mount to position and manage a radio telescope. And uses an RTLSDR to collect data and then turn it into an image!



This software would have been completely impossible without the help from Ryan Fav (Discord: ryanfav). Thank you so much!
Also, this would have been extremely hard to do without the assistance from ChatGPT v4.0 and Grok 3.0 so thank you to the team at OpenAi and Grok for making such a powerful tool!






--------HOW TO USE--------

H1.I.M.E is pretty straightforward and simple but here is a rundown on how to use it:

Also please note: while this program is available on GitHub, we'd prefer for you to not take the code and modify it for yourself. However if something isn't working and you need technical support on it, you may email or message on Discord at any time.

Fast reply email (will reply within 10 hours 24/7): morgpro1@gmail.com
Discord (will reply within 10 hours 24/7): _stormgaming


If you do wish to make your own adaptations on the code, please check with one of those contacts and ask for permission, also make sure to give credit where credit is due.



-Installation-

Please run the 'Dependencies Installer.bat' file AS ADMINISTRATOR.
This will install Python as well as the other dependencies for this program. 

Note: If the command prompt window is only a few lines long and not pages of text, and that doesn't change within about a minute, just install Python from the Microsoft Store, then run the script again.





-Data Collection-

Step 1: Run the "H1IME.py" file.

Step 2: Select the "Data Collection" mode.

Step 3: Set the ASCOM driver that your telescope uses. (If you don't know, it's probably the first one)

Step 4: Input your desired image dimension. (Grid width is # of pixels wide, grid height is # of pixels tall)

Step 5: Input grid spacing. (Use the built in calculator mode to calculate spacing, we suggest a 25-35% overlap)

Step 6: Input desired averaging time. (Going over 2 seconds may cause errors)

Step 7: Input settle time. (2 seconds works for most setups, have longer settle time for high magnification setups)

Step 8: Input center frequency, sample rate, and gain of the SDR. (Defaults work for most setups)

Step 9: Select where you want the data to be stored. (Will be a singular .JSON file)

Step 10: Press begin scan.


Note: The live visualizer to show the data recording progress may not actually represent the colors in the final image. Due to how the graph is displaying its color range, it struggles to do this dynamically while new data is arriving. However the visualizer is still usable to know image progress.



-Image Generation-

Once the data is collected and the .JSON file was generated, switch modes to "Image Assembly". Then simply press the "Select JSON File" button, select the data file that was previously generated. And it will open up a window and display the image that is generated.



-Slew Tool-

To allow ease of use, there is also a "Slew Tool", which allows you to input RA/DEC coordinates for easy slew and position control.