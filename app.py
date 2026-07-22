import streamlit as st
import psycopg2
NEON_DATABASE_URL = "postgresql://neondb_owner:npg_DRJ5nF0OTNiy@ep-rapid-morning-ajlql2xf.c-3.us-east-2.aws.neon.tech/neondb?sslmode=require"

# Page Configuration
st.set_page_config(page_title="Equipment Tracker", layout="centered")

#######################
def connect_db():
    """Establish connection to the Neon PostgreSQL database."""
    try:
        conn = psycopg2.connect(NEON_DATABASE_URL)
        return conn
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        return None

# --- Initialize App Memory (Session State) ---
if "current_page" not in st.session_state:
    st.session_state.current_page = "Home"

# Main UI Title
st.title("Warehouse Equipment Tracker")

# --- Top Navigation Buttons (Vertically Stacked) ---
if st.button("Move Equipment", use_container_width=True):
    st.session_state.current_page = "Move Equipment"

if st.button("Total Scrap-Out", use_container_width=True):
    st.session_state.current_page = "Total Scrap-Out"

if st.button("View Locations", use_container_width=True):
    st.session_state.current_page = "View Locations"

# --- Extras Menu (Fold-out Expander) ---
with st.expander("Extras Menu"):
    if st.button("Add Equipment", use_container_width=True):
        st.session_state.current_page = "Add Equipment"
    
    if st.button("Remove Equipment", use_container_width=True):
        st.session_state.current_page = "Remove Equipment"
        
    if st.button("Find Equipment", use_container_width=True):
        st.session_state.current_page = "Find Equipment"
        
    if st.button("View Logs", use_container_width=True):
        st.session_state.current_page = "View Logs"

    if st.button("Delete All Empty Jobs", use_container_width=True):
        st.session_state.current_page = "Delete Empty Jobs"

st.divider()

# --- Screen Routing ---
if st.session_state.current_page == "Home":
    st.info("Select an option above to get started.")
############### Equip Movement Section Code Block ###########################
elif st.session_state.current_page == "Move Equipment":
    st.subheader("Move Equipment")
    st.write("Transfer equipment from the Shop to a job site, or move it between locations.")
    
    # Initialize a "staging list" in the app's memory to hold items before moving
    if "move_cart" not in st.session_state:
        st.session_state.move_cart = {}

    conn = connect_db()
    if conn:
        cur = conn.cursor()
        
        # --- 1. ADD NEW JOB SITE EXPANDER ---
        with st.expander("➕ Create New Job Site"):
            with st.form("new_job_form", clear_on_submit=True):
                new_job_name = st.text_input("Enter New Job Site Name")
                submit_job = st.form_submit_button("Create Job Site")
                
                if submit_job and new_job_name:
                    try:
                        cur.execute("INSERT INTO locations (name) VALUES (%s);", (new_job_name.strip(),))
                        conn.commit()
                        st.success(f"Job site '{new_job_name.strip()}' created! You can now select it below.")
                        st.rerun() 
                    except Exception as e:
                        conn.rollback()
                        st.error("That job site name already exists.")
                        
        st.divider()
        
        # --- 2. DESTINATION SELECTION ---
        cur.execute("SELECT id, name FROM locations ORDER BY (id = 1) DESC, name ASC;")
        locations = cur.fetchall()
        loc_options = {loc[1]: loc[0] for loc in locations}
        
        selected_loc_name = st.selectbox("Select Destination Location", list(loc_options.keys()))
        target_location_id = loc_options[selected_loc_name]

        st.divider()

        # --- 3. SELECT EQUIPMENT (TWO-STEP FILTER WITH MOBILE SEARCH) ---
        if target_location_id:
            st.write(f"### Moving gear to: **{selected_loc_name}**")
            
            cur.execute("""
                SELECT DISTINCT et.id, et.name 
                FROM equipment_types et 
                JOIN equipment e ON et.id = e.type_id 
                ORDER BY et.name
            """)
            avail_types = cur.fetchall()
            
            if avail_types:
                type_options = {t[1]: t[0] for t in avail_types}
                
                # Mobile-friendly category search filter
                search_query = st.text_input("🔍 Type to Filter Categories", "", key="move_category_search").strip().lower()
                filtered_options = {name: val for name, val in type_options.items() if search_query in name.lower()}
                
                if filtered_options:
                    selected_type_name = st.selectbox("1. Select Equipment Type", list(filtered_options.keys()), key="move_category_selectbox")
                    selected_type_id = filtered_options[selected_type_name]
                else:
                    st.warning("No categories match your search.")
                    selected_type_id = None
                
                if selected_type_id:
                    # Step B: Fetch only the Units for the selected Category
                    cur.execute("""
                        SELECT e.id, e.unit_number, l.name 
                        FROM equipment e 
                        JOIN locations l ON e.location_id = l.id 
                        WHERE e.type_id = %s
                        ORDER BY e.unit_number
                    """, (selected_type_id,))
                    items = cur.fetchall()
                    
                    # Filter out items that the user has already added to their staging list
                    available_items = [i for i in items if i[0] not in st.session_state.move_cart]
                    
                    if available_items:
                        item_options = {}
                        for item in available_items:
                            i_id, u_num, loc_name = item
                            label = f"{u_num} (Currently at: {loc_name})"
                            item_options[label] = i_id
                            
                        selected_item_label = st.selectbox("2. Select Specific Item", list(item_options.keys()), key="move_item_selectbox")
                        
                        # Add to list button with unique key
                        if st.button("➕ Add to List", key="add_to_move_list_btn"):
                            item_id = item_options[selected_item_label]
                            full_label = f"{selected_type_name} — {selected_item_label}"
                            st.session_state.move_cart[item_id] = full_label
                            st.rerun()
                    else:
                        st.info(f"All available {selected_type_name}s are already on your move list.")

            # --- 4. STAGING LIST & CONFIRMATION ---
            if st.session_state.move_cart:
                st.divider()
                st.write("### 📋 Items Ready to Move:")
                
                for idx, (i_id, label) in enumerate(st.session_state.move_cart.items()):
                    st.write(f"- {label}")
                    
                st.write("") 
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🚚 Confirm & Move All", use_container_width=True):
                        try:
                            for item_id, label in st.session_state.move_cart.items():
                                cur.execute("""
                                    SELECT et.name, e.unit_number 
                                    FROM equipment e 
                                    JOIN equipment_types et ON e.type_id = et.id 
                                    WHERE e.id = %s
                                """, (item_id,))
                                t_name, u_num = cur.fetchone()
                                item_desc = f"{t_name} ({u_num})" if u_num != "N/A" else t_name
                                
                                cur.execute("UPDATE equipment SET location_id = %s WHERE id = %s", (target_location_id, item_id))
                                
                                cur.execute("""
                                    INSERT INTO movement_logs (action_type, item_description, target_location) 
                                    VALUES (%s, %s, %s)
                                """, ("MOVED", item_desc, selected_loc_name))
                                
                            conn.commit()
                            st.session_state.move_cart.clear() 
                            st.success("Successfully moved all equipment!")
                            st.rerun()
                        except Exception as e:
                            conn.rollback()
                            st.error(f"Error moving equipment: {e}")
                            
                with col2:
                    if st.button("❌ Clear List", use_container_width=True):
                        st.session_state.move_cart.clear()
                        st.rerun()
                        
        cur.close()
        conn.close()
########################################
elif st.session_state.current_page == "Total Scrap-Out":
    st.subheader("Total Scrap-Out")
    st.write("Return all equipment from a specific job site back to the Shop at once.")
    
    conn = connect_db()
    if conn:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT DISTINCT l.id, l.name 
            FROM locations l
            JOIN equipment e ON l.id = e.location_id
            WHERE l.id != 1
            ORDER BY l.name;
        """)
        active_jobs = cur.fetchall()
        
        if active_jobs:
            job_options = {job[1]: job[0] for job in active_jobs}
            selected_job_name = st.selectbox("Select Job Site to Scrap Out", list(job_options.keys()))
            selected_job_id = job_options[selected_job_name]
            
            st.warning(f"Warning: This will instantly move all equipment currently at '{selected_job_name}' back to the Shop.")
            
            if st.button("Confirm Total Scrap-Out"):
                try:
                    cur.execute("""
                        SELECT e.id, et.name, e.unit_number 
                        FROM equipment e 
                        JOIN equipment_types et ON e.type_id = et.id 
                        WHERE e.location_id = %s
                    """, (selected_job_id,))
                    items_to_move = cur.fetchall()
                    
                    cur.execute("UPDATE equipment SET location_id = 1 WHERE location_id = %s", (selected_job_id,))
                    
                    for item in items_to_move:
                        item_id, t_name, u_num = item
                        item_desc = f"{t_name} ({u_num})" if u_num != "N/A" else t_name
                        
                        cur.execute("""
                            INSERT INTO movement_logs (action_type, item_description, target_location) 
                            VALUES (%s, %s, %s)
                        """, ("SCRAP-OUT", item_desc, f"Returned to Shop from {selected_job_name}"))
                        
                    conn.commit()
                    st.success(f"Successfully returned {len(items_to_move)} items from {selected_job_name} back to the Shop!")
                    st.rerun()
                    
                except Exception as e:
                    conn.rollback()
                    st.error(f"Error during scrap-out: {e}")
        else:
            st.info("There are currently no active job sites with equipment to scrap out.")
            
        cur.close()
        conn.close()
#################### Location View Code #########################
elif st.session_state.current_page == "View Locations":
    st.subheader("Current Locations")
    st.write("View all equipment currently assigned to the Shop or active job sites.")
    
    conn = connect_db()
    if conn:
        cur = conn.cursor()
        
        cur.execute("SELECT id, name FROM locations ORDER BY (id = 1) DESC, name ASC;")
        locations = cur.fetchall()
        
        if locations:
            loc_options = {loc[1]: loc[0] for loc in locations}
            selected_loc_name = st.selectbox("Select a Location to View", list(loc_options.keys()))
            selected_loc_id = loc_options[selected_loc_name]
            
            st.divider()
            
            cur.execute("""
                SELECT et.name, e.unit_number, et.has_number
                FROM equipment e
                JOIN equipment_types et ON e.type_id = et.id
                WHERE e.location_id = %s
                ORDER BY et.name, e.unit_number
            """, (selected_loc_id,))
            
            inventory = cur.fetchall()
            
            if inventory:
                st.write(f"### Inventory at: {selected_loc_name}")
                
                display_data = {}
                for item in inventory:
                    type_name = item[0]
                    unit_num = item[1]
                    has_number = item[2]
                    
                    if type_name not in display_data:
                        display_data[type_name] = {"has_number": has_number, "items": [], "count": 0}
                        
                    display_data[type_name]["count"] += 1
                    if has_number and unit_num != "N/A":
                        display_data[type_name]["items"].append(unit_num)
                        
                for type_name, data in display_data.items():
                    if data["has_number"]:
                        # Fixed numeric sorting order
                        items_list = ", ".join(sorted(data["items"], key=lambda x: int(x) if x.isdigit() else x))
                        st.write(f"**{type_name}** (Total Count: {data['count']})")
                        st.write(f"Assigned Units: {items_list}")
                    else:
                        st.write(f"**{type_name}** (Quantity: {data['count']})")
                    
                    st.write("---") 
            else:
                st.info(f"No equipment currently located at {selected_loc_name}.")
        else:
            st.info("No locations found in the database.")
            
        cur.close()
        conn.close()
########################


####################### Adding Eqiuipment Section Code Block
elif st.session_state.current_page == "Add Equipment":
    st.subheader("Add New Equipment")
    st.write("Register new equipment. All new items are automatically placed in the Shop.")
    
    conn = connect_db()
    if conn:
        cur = conn.cursor()
        
        st.write("Step 1: Define Equipment Category (if it doesn't exist yet)")
        with st.form("new_type_form", clear_on_submit=True):
            type_name = st.text_input("Category Name (e.g., Grinder, Extension Cord)")
            has_number = st.checkbox("Does this item use unit numbers? (Uncheck for bulk items)", value=True)
            submit_type = st.form_submit_button("Create Category")
            
            if submit_type and type_name:
                try:
                    cur.execute("INSERT INTO equipment_types (name, has_number) VALUES (%s, %s)", (type_name, has_number))
                    conn.commit()
                    st.success(f"Category '{type_name}' created successfully.")
                except Exception as e:
                    st.error("That category might already exist.")
                    conn.rollback()

        st.divider()

        st.write("Step 2: Add Item to Inventory")
        
        cur.execute("SELECT id, name, has_number FROM equipment_types")
        types = cur.fetchall()
        
        if types:
            type_options = {t[1]: t for t in types}
            
            selected_type_name = st.selectbox("Select Category", list(type_options.keys()))
            selected_type = type_options[selected_type_name]
            
            type_id = selected_type[0]
            category_has_number = selected_type[2]
            
            with st.form("new_equipment_form", clear_on_submit=True):
                if category_has_number:
                    unit_number = st.text_input("Unit Number (Required)")
                    quantity = 1
                else:
                    unit_number = "N/A"
                    quantity = st.number_input("Quantity to Add", min_value=1, value=1, step=1)
                
                submit_eq = st.form_submit_button("Add to Shop")
                
                if submit_eq:
                    if category_has_number and not unit_number.strip():
                        st.error("A unit number is required for this category.")
                    else:
                        duplicate_found = False
                        if category_has_number:
                            cur.execute("SELECT id FROM equipment WHERE unit_number = %s", (unit_number.strip(),))
                            if cur.fetchone():
                                duplicate_found = True
                                st.error(f"Error: Unit number '{unit_number}' already exists in the system.")
                        
                        if not duplicate_found:
                            try:
                                for _ in range(quantity):
                                    cur.execute("""
                                        INSERT INTO equipment (type_id, unit_number, location_id) 
                                        VALUES (%s, %s, 1)
                                    """, (type_id, unit_number.strip() if category_has_number else "N/A"))
                                    
                                    conn.commit()
                                    
                                if category_has_number:
                                    st.success(f"Successfully added {selected_type_name} (Unit: {unit_number}) to the Shop.")
                                else:
                                    st.success(f"Successfully added {quantity} x {selected_type_name} to the Shop.")
                                    
                            except Exception as e:
                                st.error(f"Error adding equipment: {e}")
                                conn.rollback()
        else:
            st.info("Please create at least one equipment category above before adding items.")
            
        cur.close()
        conn.close()
########################

######## Eq Remove block ###################
elif st.session_state.current_page == "Remove Equipment":
    st.subheader("Decommission Equipment")
    st.write("Remove broken or retired equipment from the active list.")
    
    if "remove_cart" not in st.session_state:
        st.session_state.remove_cart = {}

    conn = connect_db()
    if conn:
        cur = conn.cursor()
        
        cur.execute("""
            SELECT DISTINCT et.id, et.name 
            FROM equipment_types et 
            JOIN equipment e ON et.id = e.type_id 
            ORDER BY et.name
        """)
        avail_types = cur.fetchall()
        
        if avail_types:
            type_options = {t[1]: t[0] for t in avail_types}
            selected_type_name = st.selectbox("1. Select Equipment Type", list(type_options.keys()))
            selected_type_id = type_options[selected_type_name]
            
            cur.execute("""
                SELECT e.id, e.unit_number, l.name 
                FROM equipment e 
                JOIN locations l ON e.location_id = l.id 
                WHERE e.type_id = %s
                ORDER BY e.unit_number
            """, (selected_type_id,))
            items = cur.fetchall()
            
            available_items = [i for i in items if i[0] not in st.session_state.remove_cart]
            
            if available_items:
                item_options = {}
                for item in available_items:
                    i_id, u_num, loc_name = item
                    label = f"{u_num} (Currently at: {loc_name})"
                    item_options[label] = i_id
                    
                selected_item_label = st.selectbox("2. Select Specific Item to Remove", list(item_options.keys()))
                
                # Unique key assigned here
                if st.button("Add to Removal List", key="add_to_remove_list_btn"):
                    item_id = item_options[selected_item_label]
                    full_label = f"{selected_type_name} — {selected_item_label}"
                    st.session_state.remove_cart[item_id] = full_label
                    st.rerun()
            else:
                st.info(f"All available {selected_type_name}s are already on your removal list.")

        if st.session_state.remove_cart:
            st.divider()
            st.write("### Items Ready for Removal:")
            
            for idx, (i_id, label) in enumerate(st.session_state.remove_cart.items()):
                st.write(f"- {label}")
                
            st.write("") 
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Confirm & Remove All", use_container_width=True):
                    try:
                        for item_id, label in st.session_state.remove_cart.items():
                            cur.execute("""
                                SELECT et.name, e.unit_number, l.name
                                FROM equipment e 
                                JOIN equipment_types et ON e.type_id = et.id 
                                JOIN locations l ON e.location_id = l.id
                                WHERE e.id = %s
                            """, (item_id,))
                            t_name, u_num, loc_name = cur.fetchone()
                            item_desc = f"{t_name} ({u_num})" if u_num != "N/A" else t_name
                            
                            cur.execute("DELETE FROM equipment WHERE id = %s", (item_id,))
                            
                            cur.execute("""
                                INSERT INTO movement_logs (action_type, item_description, target_location) 
                                VALUES (%s, %s, %s)
                            """, ("REMOVED", item_desc, f"Removed from {loc_name}"))
                            
                        conn.commit()
                        st.session_state.remove_cart.clear()
                        st.success("Successfully removed selected equipment!")
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Error removing equipment: {e}")
                        
            with col2:
                if st.button("Clear List", use_container_width=True):
                    st.session_state.remove_cart.clear()
                    st.rerun()
                    
        cur.close()
        conn.close()

elif st.session_state.current_page == "Find Equipment":
    st.subheader("Find Equipment")
    st.write("Locate specific equipment or view distribution across all sites.")
    
    conn = connect_db()
    if conn:
        cur = conn.cursor()
        
        cur.execute("SELECT id, name, has_number FROM equipment_types ORDER BY name")
        types = cur.fetchall()
        
        if types:
            type_options = {t[1]: {"id": t[0], "has_number": t[2]} for t in types}
            selected_type_name = st.selectbox("Select Equipment Type", list(type_options.keys()))
            selected_type = type_options[selected_type_name]
            
            st.divider()
            
            if selected_type["has_number"]:
                cur.execute("""
                    SELECT e.unit_number, l.name 
                    FROM equipment e
                    JOIN locations l ON e.location_id = l.id
                    WHERE e.type_id = %s
                    ORDER BY e.unit_number
                """, (selected_type["id"],))
                units = cur.fetchall()
                
                if units:
                    unit_options = {u[0]: u[1] for u in units}
                    selected_unit = st.selectbox("Select Number", list(unit_options.keys()))
                    st.write(f"### Location: **{unit_options[selected_unit]}**")
                else:
                    st.info(f"No {selected_type_name}s found in the system.")
            else:
                cur.execute("""
                    SELECT l.name, COUNT(e.id) 
                    FROM equipment e
                    JOIN locations l ON e.location_id = l.id
                    WHERE e.type_id = %s
                    GROUP BY l.name
                    ORDER BY l.name
                """, (selected_type["id"],))
                counts = cur.fetchall()
                
                if counts:
                    st.write(f"### {selected_type_name} Distribution:")
                    for loc_name, count in counts:
                        st.write(f"- **{loc_name}**: {count}")
                else:
                    st.info(f"No {selected_type_name}s found in the system.")
        else:
            st.info("No equipment types found.")
            
        cur.close()
        conn.close()
#############################
elif st.session_state.current_page == "Delete Empty Jobs":
    st.subheader("Delete All Empty Jobs")
    st.write("Permanently remove all job sites that currently have 0 equipment assigned.")
    
    st.divider()
    
    if "confirm_delete_empty" not in st.session_state:
        st.session_state.confirm_delete_empty = False

    if st.button("Delete All Empty Jobs"):
        st.session_state.confirm_delete_empty = True

    if st.session_state.confirm_delete_empty:
        st.warning("Are you sure? This will permanently delete all job sites with 0 equipment assigned (The Shop will not be touched).")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes, Delete Empty Jobs", use_container_width=True):
                conn = connect_db()
                if conn:
                    cur = conn.cursor()
                    try:
                        cur.execute("""
                            DELETE FROM locations 
                            WHERE id != 1 
                            AND id NOT IN (SELECT DISTINCT location_id FROM equipment);
                        """)
                        deleted_count = cur.rowcount
                        conn.commit()
                        st.success(f"Successfully cleaned up {deleted_count} empty job sites!")
                        st.session_state.confirm_delete_empty = False
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Error deleting empty jobs: {e}")
                    finally:
                        cur.close()
                        conn.close()
        with col2:
            if st.button("Cancel", use_container_width=True):
                st.session_state.confirm_delete_empty = False
                st.rerun()

###### Log View Section ########################
elif st.session_state.current_page == "View Logs":
    st.subheader("Activity Logs")
    st.write("View the recent history of equipment movement and inventory changes.")
    
    conn = connect_db()
    if conn:
        cur = conn.cursor()
        
        try:
            cur.execute("""
                SELECT action_type, item_description, target_location 
                FROM movement_logs 
                ORDER BY id DESC 
                LIMIT 100
            """)
            logs = cur.fetchall()
            
            if logs:
                log_data = []
                for row in logs:
                    log_data.append({
                        "Action": row[0],
                        "Equipment": row[1],
                        "Location / Note": row[2]
                    })
                
                st.dataframe(log_data, use_container_width=True)
            else:
                st.info("No activity logs found. Start moving or removing equipment to see history here.")
                
        except Exception as e:
            st.error(f"Error fetching logs: {e}")
            
        cur.close()
        conn.close()
