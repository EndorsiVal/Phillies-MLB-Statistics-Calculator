
from typing import Union
import re
from dataclasses import dataclass
from tkinter import ttk
import tkinter as tk
import pkgutil
from pathlib import Path
import io
import tempfile
from threading import Thread

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageTk


# For creating the executable pyinstaller was used.
# https://datatofish.com/executable-pyinstaller/

@dataclass(frozen=True)
class Player:
    """Class for representing a player with a salary"""
    
    name: str
    salary: Union[int, str]
    year: str
    level: str
    
    def __str__(self):
        if isinstance(self.salary, int):
            salary = display_salary(self.salary)
        else:
            salary = self.salary
        return f"Name: {self.name}\nSalary: {salary}\nYear: {self.year}\nLevel: {self.level}\n"

PAGE_URL = 'https://questionnaire-148920.appspot.com/swe/data.html'
SALARY_RE = re.compile(r"^\$*\d+(\,?\d+)*$")
N_FIRST_N_HIGHEST_EARNERS = 3

# Returns the dataset page parsed as a BeautifulSoup object
def crawl_page():
    page = requests.get(PAGE_URL)
    
    if page.status_code != 200:
        raise Exception('Could not retrieve data set. Try again by running the script again.')
    
    return BeautifulSoup(page.text, 'html.parser')

# Returns a list of players from a parsed web page
def extract_players(soup):
    salary_columns = soup.select('tbody tr')
    
    players = []
    for row in salary_columns:
        players.append(extract_player(row))
    
    return players

# Returns a player from a tr element
def extract_player(tr):
    elements = [tr.select_one(f'td.player-{e}') for e in ('name', 'salary', 'year', 'level')]
    name, salary, year, level = [e.text for e in elements]
    
    m_salary = SALARY_RE.search(salary)
    if m_salary:
        salary = int(salary.replace('$', '').replace(',', '').replace(' ', ''))
    else:
        salary = 'No data found'
    return Player(name, salary, year, level)

# Inserts a value in an array orderly, 
# by using gt to compare if the value is greater 
# than any element in the array
def insert_in_limited_array(value, gt, array):
    for i in range(len(array)):
        item = array[i]
        if item is None or gt(value, item):
            # insert value in the ordered array
            array.insert(i, value)
            # remove last item
            array.pop()
            return

# Gets average of values given by applying get_value to each element in array
def average(array, get_value):
    length = len(array)
    total = 0
    for x in array:
        if x is not None:
            total += get_value(x)
    
    return total / length

# Returns a suitable string representation of a monetary value
def display_salary(salary):
    buffer = []
    n = salary
    while n:
        buffer.append(int(n % 1000))
        n //= 1000
    
    buffer = buffer[::-1]
    buffer = [str(buffer[0]), *['{:03d}'.format(x) for x in buffer[1:]]]
    
    return '$' + ','.join(buffer)

class App(tk.Frame):
    
    def __init__(self, master, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.grid()
        
        self.players = []
        self.avg = 0
        self.n_of_corrupted_salaries = 0
        self.highest_salaries_125 = [None]*125
        
        self.bind('<<update>>', self.update_display)
        
        try:
            img_data = pkgutil.get_data('img', 'Phillies.png')
        except ImportError:
            pass
        
        if img_data is None:
            with Path(__file__).parent.joinpath('img', 'Phillies.png').open('rb') as f:
                img_data = f.read()
                
        with io.BytesIO(img_data) as f:
            f.seek(0)
            f.name = 'Phillies.png'
            img = Image.open(f)
            img.thumbnail((256, 256))
            render = ImageTk.PhotoImage(img)
            self.img = img
            self.render = render
        img = tk.Label(self, image=render)
        img.grid()
            
        
        
        btn = tk.Button(self, text="Get statistics", command=self.crawl_and_update)
        btn.grid()
        self.btn = btn
        
        self.text_n_corrupted = tk.StringVar()
        self.text_n_corrupted.set("Number of corrupted salaries in dataset: No data")
        
        self.text_expected_salary = tk.StringVar()
        self.text_expected_salary.set("Expected Offer Value: No data")
        
        self.text_n_highest_earners = [tk.StringVar() for i in range(N_FIRST_N_HIGHEST_EARNERS)]
        for x in self.text_n_highest_earners:
            x.set("No data")
        
        t = tk.Label(self, textvariable=self.text_n_corrupted)
        t.grid()
        
        t = tk.Label(self, textvariable=self.text_expected_salary)
        t.grid()
        
        tk.Label(self, text=f'Top {N_FIRST_N_HIGHEST_EARNERS} highest earners').grid()
        for i, x in enumerate(self.text_n_highest_earners):
            tk.Label(self, text=f"{i+1}.-").grid()
            t = tk.Label(self, textvariable=x)
            t.grid()
        
    # Gets statistics and update UI with new info
    def crawl_and_update(self):
        def f():
            self.crawl_players()
            self.event_generate('<<update>>', when='tail')
        
        # disable the button so that multiple requests aren't sent
        self.btn['state'] = tk.DISABLED
        
        # use a thread to keep the ui from being unresponsive
        th = Thread(target=f)
        th.start()
    
    # return a list of Player that correspond to the Top N highest salaries
    def top_highest_salaries(self):
        return self.highest_salaries_125[:N_FIRST_N_HIGHEST_EARNERS]
    
    # Updates the UI to show the updated information
    def update_display(self, *_):
        # Re enable the button to make new requests in the future
        self.btn['state'] = tk.NORMAL
        
        self.text_n_corrupted.set(f"Number of corrupted salaries in dataset: {self.n_of_corrupted_salaries}")
        avg = display_salary(self.avg)
        self.text_expected_salary.set(f"Expected Offer Value: {avg}")
        
        for p, x in zip(self.top_highest_salaries(),self.text_n_highest_earners):
            if p is None:
                x.set('No data')
            else:
                x.set(str(p))
    
    # Gets dataset from the webpage and processes it
    def crawl_players(self):
        page = crawl_page()
        players = extract_players(page)
        
        highest_salaries_125 = [None]*125
        
        
        n_of_corrupted_salaries = 0
        for p in players:
            if isinstance(p.salary, int):
                insert_in_limited_array(p, lambda a, b: a.salary > b.salary, highest_salaries_125)
            else:
                n_of_corrupted_salaries += 1
                
        
        self.avg = average(highest_salaries_125, lambda x: x.salary)
        self.n_of_corrupted_salaries = n_of_corrupted_salaries
        self.players = players
        self.highest_salaries_125 = highest_salaries_125
        
    
    
    
def main():
    root = tk.Tk()
    app = App(root)
    
    root.mainloop()

if __name__=='__main__':
    main()
    
    
