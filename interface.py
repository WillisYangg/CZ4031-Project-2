import tkinter as tk
from tkinter import *
from PIL import Image, ImageTk
from explain import *
from pprint import pprint

class Window:
    def __init__(self, master):
        # Get window dimensions
        self.width = master.winfo_screenwidth()
        self.height = master.winfo_screenheight()

        # build entry frame
        self.frame_entry = Frame(master, background="red")
        self.label_input1 = Label(self.frame_entry, text="Query 1:")
        self.entry1 = Text(self.frame_entry, height=10, width=30)
        self.label_input2 = Label(self.frame_entry, text="Query 2:")
        self.entry2 = Text(self.frame_entry, height=10, width=30)
        
        # Build and pack button
        self.control_frame = Frame(master, background="yellow")
        self.button1 = Button(self.control_frame, text="Submit", command=self.run)
        self.button1.pack(expand=True, fill=BOTH)
        self.control_frame.pack(padx=10, pady=10, side=BOTTOM, expand=True, fill=BOTH)
        
        # Build and pack display text
        self.frame3 = Frame(master, background="green", width= self.width, height= self.height/5,)
        self.sql_label = Label(self.frame3, text="SQL Differences:").pack(side=LEFT, fill=BOTH)
        self.textbox_sql = Text(self.frame3, height=50, width=50, state="disabled")
        self.textbox_sql.pack(side=LEFT, expand=True, fill=X)
        self.qep_label = Label(self.frame3, text="    QEP Differences:").pack(side=LEFT, fill=BOTH)
        self.textbox_qep = Text(self.frame3, height=50, width=50, state="disabled")
        self.textbox_qep.pack(side=LEFT, expand=True, fill=X)
        self.frame3.pack(padx=10, pady=10, side=BOTTOM, expand=True)
        self.frame3.pack_propagate(False)

        # packing entry frames
        self.label_input1.pack(fill=BOTH)
        self.entry1.pack(expand=True, fill=BOTH)
        self.label_input2.pack(fill=BOTH)
        self.entry2.pack(expand=True, fill=BOTH)
        self.frame_entry.pack(padx=10, pady=10, side=LEFT, expand=True, fill=BOTH)
        
        # Build and pack images
        self.frame_diagram = Frame(master, background="red")
        self.query1_label = Label(self.frame_diagram, text="Query 1:").pack(fill=BOTH)
        self.image_scroll1 = ScrollableImage(self.frame_diagram, scrollbarwidth=20, width=self.width/3, height=self.height/4)
        self.image_scroll1.pack(expand=TRUE, fill=BOTH)
        self.query2_label = Label(self.frame_diagram, text="Query 2:").pack(fill=BOTH)
        self.image_scroll2 = ScrollableImage(self.frame_diagram, scrollbarwidth=20, width=self.width/3, height=self.height/4)
        self.image_scroll2.pack(expand=TRUE, fill=BOTH)
        self.frame_diagram.pack(padx=10, pady=10, side=RIGHT, expand=TRUE, fill=BOTH)

    def clear_frame(self, frame):
        for widgets in frame.winfo_children():
            widgets.destroy()

    def update_image_frame(self, frame):
        # Remove current images
        self.clear_frame(frame)
        # Load new images
        query1 = ImageTk.PhotoImage(Image.open("query1.png").resize((int(self.width/1.5),int(self.height/1.5))))
        query2 = ImageTk.PhotoImage(Image.open("query2.png").resize((int(self.width/1.5),int(self.height/1.5))))
        # Rebuild frame
        self.query1_label = Label(self.frame_diagram, text="Query 1:").pack(expand=True, fill=BOTH)
        self.image_scroll1 = ScrollableImage(self.frame_diagram, image=query1, scrollbarwidth=20, width=self.width/3, height=self.height/4)
        self.image_scroll1.pack(expand=TRUE, fill=BOTH)
        self.query2_label = Label(self.frame_diagram, text="Query 2:").pack(expand=True, fill=BOTH)
        self.image_scroll2 = ScrollableImage(self.frame_diagram, image=query2, scrollbarwidth=20, width=self.width/3, height=self.height/4)
        self.image_scroll2.pack(expand=TRUE, fill=BOTH)

    def update_output(self, sql, qep):
        # unlock textboxes
        self.textbox_qep.config(state="normal")
        self.textbox_sql.config(state="normal")
        # clear textboxes
        self.textbox_qep.delete("1.0", END)
        self.textbox_sql.delete("1.0", END)
        # update textboxes
        self.textbox_qep.insert(END, qep)
        self.textbox_sql.insert(END, sql)
        # lock textboxes
        self.textbox_qep.config(state="disabled")
        self.textbox_sql.config(state="disabled")

    def get_input(self):
        prefix = "set max_parallel_workers_per_gather =0;\n" \
                 "EXPLAIN (VERBOSE, ANALYZE, FORMAT JSON)\n"
        entry1 = prefix + self.entry1.get("1.0", 'end-1c')
        entry2 = prefix + self.entry2.get("1.0", 'end-1c')
        entry1 = entry1.lower()
        entry2 = entry2.lower()
        return entry1, entry2

    def run(self):
        # Check if input is empty
        if len(self.entry1.get("1.0", END)) == 1 or len(self.entry2.get("1.0", END)) == 1:
            self.update_output("Please fill in both Query 1 and Query 2", "Please fill in both Query 1 and Query 2")
            return

        # Get input
        entry1, entry2 = self.get_input()

        # Create QEP
        connection = connect_db()
        try:
            q1_root = buildQEP(execute_json(connection, entry1))
        except:
            self.update_output("There are errors in Query 1. Please try again",
                               "There are errors in Query 1. Please try again")
            return
        try:
            q2_root = buildQEP(execute_json(connection, entry2))
        except:
            self.update_output("There are errors in Query 2. Please try again",
                               "There are errors in Query 2. Please try again")
            return

        # find sql query differences
        query_diff = query_difference(parseSQL(entry1), parseSQL(entry2))
        query_diff_natural_language = sql_diff_to_natural_language(query_diff)

        # algo to find the sequential changes to convert QEP1 into QEP2
        _, qep_diff = get_path_difference(q1_root, q2_root)

        # natural language output strings
        # SQL differences
        sql_text = convert_to_text(query_diff_natural_language)
        # QEP differences
        qep_diff_natural_language = diff_to_natural_language(qep_diff, query_diff)
        qep_text = convert_to_text(qep_diff_natural_language)

        # Generate QEP images
        QEP_dfs(q1_root, "query1")
        QEP_dfs(q2_root, "query2")

        # Update GUI
        self.update_image_frame(self.frame_diagram)
        self.update_output(sql_text, qep_text)
        

# https://stackoverflow.com/questions/56043767/show-large-image-using-scrollbar-in-python
# Widget for scrollable images
class ScrollableImage(tk.Frame):
    def __init__(self, master=None, **kw):
        # Set image
        self.image = kw.pop('image', None)
        # Set scrollbar width
        sw = kw.pop('scrollbarwidth', 20)
        super(ScrollableImage, self).__init__(master=master, **kw)
        self.cnvs = Canvas(self, highlightthickness=0, **kw)
        self.cnvs.create_image(0, 0, anchor='nw', image=self.image)
        # Vertical and Horizontal scrollbars
        self.v_scroll = Scrollbar(self, orient='vertical', width=sw)
        self.h_scroll = Scrollbar(self, orient='horizontal', width=sw)
        # Grid and configure weight.
        self.cnvs.grid(row=0, column=0,  sticky='nsew')
        self.h_scroll.grid(row=1, column=0, sticky='ew')
        self.v_scroll.grid(row=0, column=1, sticky='ns')
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        # Set the scrollbars to the canvas
        self.cnvs.config(xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set)
        # Set canvas view to the scrollbars
        self.v_scroll.config(command=self.cnvs.yview)
        self.h_scroll.config(command=self.cnvs.xview)
        # Assign the region to be scrolled
        self.cnvs.config(scrollregion=self.cnvs.bbox('all'))


if __name__ == "__main__":
    root = Tk()
    root.title("Query Descriptor ")
    root.state("zoomed")
    window = Window(root)
    root.mainloop()
