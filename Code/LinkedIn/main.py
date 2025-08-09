from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import subprocess
import csv
import re
from selenium.webdriver.support.ui import Select
import random 

def human_delay(min_sec=1, max_sec=3):
    delay = random.uniform(min_sec, max_sec)
    print(f"delay of {delay:.3f}s ...")
    time.sleep(delay)

def human_type(element, text, min_delay=0.05, max_delay=0.15):
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(min_delay, max_delay))

    human_delay()

def ask_llm_1(question, driver) -> str:
    try:
        prompt = f"Answer this job application question briefly and clearly:\n{question}"

        # Run ollama model via subprocess
        result = subprocess.run(
            ["ollama", "run", "linkedin_hr"],
            input=prompt.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120
        )

        if result.returncode != 0:
            print(f"⚠️ Ollama error: {result.stderr.decode('utf-8')}")
            return "N/A"

        response = result.stdout.decode("utf-8").strip()

        # This regex captures numbers with optional commas
        print(f"🧠 LLM Response: {response}")
        response = re.findall(r'\b\d{1,3}(?:,\d{2,3})*\b|\b\d+\b', response)[0]
        print(f'Modified Response: {response}')
        # Convert to plain number (remove commas) and optionally to int
        # response = [int(match.replace(',', '')) for match in matches]
        return response

    except subprocess.TimeoutExpired:
        dismiss_post_apply_popup(driver)
        print("⏰ Ollama call timed out")
        return "N/A"
    except Exception as e:
        dismiss_post_apply_popup(driver)
        print(f"❌ Error calling ollama: {e}")
        return "N/A"

def ask_llm_2(question, options_list) -> str:
    try:
        prompt = f"""You are helping fill out a job application form. 
                    Question: "{question}"
                    Options: {options_list}
                    Which is the most appropriate answer? Just return the text of the most suitable option.
                    """

        # Run ollama model via subprocess
        result = subprocess.run(
            ["ollama", "run", "linkedin_hr"],
            input=prompt.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120
        )

        if result.returncode != 0:
            print(f"⚠️ Ollama error: {result.stderr.decode('utf-8')}")
            return "N/A"

        response = result.stdout.decode("utf-8").strip()

        # This regex captures numbers with optional commas
        print(f"🧠 LLM Response: {response}")
        return response.strip()

    except subprocess.TimeoutExpired:
        print("⏰ Ollama call timed out")
        return "N/A"
    except Exception as e:
        print(f"❌ Error calling ollama: {e}")
        return "N/A"

def setup_driver():
    options = Options()
    options.add_experimental_option("debuggerAddress", "localhost:9222")
    driver = webdriver.Edge(options=options)
    return driver

def wait_for_job_cards(driver):
    print("⏳ Waiting for job cards to load...")
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'li[id^="ember"]'))
    )

def scroll_to_element(driver, element):
    driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth', block:'center'});", element)
    human_delay(1,5)

def fill_dynamic_form(driver):
    print("🧠 Handling dynamic form step")

    # handling text fields
    text_fields = driver.find_elements(By.CSS_SELECTOR, 'div[data-test-single-line-text-form-component]')

    for field in text_fields:
        try:
            label = field.find_element(By.TAG_NAME, "label").text.strip()
            print(f"📝 Question: {label}")
            answer = ask_llm_1(label, driver)

            # Try text input
            try:
                input_field = field.find_element(By.TAG_NAME, "input")
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'})", input_field)
                input_field.clear()
                # input_field.send_keys(answer)
                human_type(input_field, answer)
                print(f"✍️  Filled: {answer}")
                continue
            except:
                dismiss_post_apply_popup(driver)
        except Exception as e:
            dismiss_post_apply_popup(driver)
            print("⚠️ Error handling form field:", e)

    # handling radio button
    try:
        radio_groups = driver.find_elements(
            By.CSS_SELECTOR,
            'fieldset[data-test-form-builder-radio-button-form-component="true"]'
        )

        for group in radio_groups:
            try:
                # Extract question
                legend = group.find_element(By.TAG_NAME, "legend")
                question_text = legend.text.strip()

                # Extract options
                option_labels = group.find_elements(By.CSS_SELECTOR, 'label[data-test-text-selectable-option__label]')
                options = [label.text.strip() for label in option_labels]

                if not question_text or not options:
                    dismiss_post_apply_popup(driver)
                    print(f"⚠️ Skipping incomplete group")
                    continue

                # Ask LLM for best option
                selected_text = ask_llm_2(question_text, options)

                # Try to click the appropriate radio
                for label in option_labels:
                    if label.text.strip().lower() == selected_text.lower():
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'})", label)
                        label.click()
                        print(f"✅ Selected: {selected_text}")
                        human_delay(1,3)
                        break
                else:
                    dismiss_post_apply_popup(driver)
                    print(f"⚠️ No matching option found for: {selected_text}")

            except Exception as e:
                dismiss_post_apply_popup(driver)
                print(f"⚠️ Failed to select 'Yes': {e}")
    except Exception as e:
        dismiss_post_apply_popup(driver)
        print(f"⚠️ Can't find radio buttons: {e}")

    # handling dropdown lists
    try:
        dropdowns = driver.find_elements(By.CSS_SELECTOR, "select[data-test-text-entity-list-form-select]")
        print(f"🔽 Found {len(dropdowns)} dropdown(s)")

        for dropdown in dropdowns:
            select = Select(dropdown)
            options_text = [o.text.strip() for o in select.options]

            # Choose "Yes" if available, else first valid option (not "Select an option")
            selected = False
            for option in select.options:
                val = option.text.strip().lower()
                if val == "yes":
                    select.select_by_visible_text(option.text)
                    selected = True
                    break
            if not selected:
                for option in select.options:
                    if "select an option" not in option.text.lower():
                        select.select_by_visible_text(option.text)
                        break
        print("✅ Dropdown(s) filled")
    except Exception as e:
        dismiss_post_apply_popup(driver)
        print(f"⚠️ Error selecting dropdown option: {e}")


    human_delay(2,5)

def handle_discard_popup(driver):
    try:
        print("🔍 Checking for discard/save popup...")
        # Wait briefly to allow the popup to appear
        WebDriverWait(driver, 3).until(
            EC.presence_of_element_located(
                (By.XPATH, "//button/span[text()='Discard']")
            )
        )
        discard_button = driver.find_element(
            By.XPATH, "//button/span[text()='Discard']/parent::button"
        )
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'})", discard_button)
        discard_button.click()
        print("🗑️ Discarded application confirmation")
        human_delay(1,5)
    except Exception as e:
        print("✅ No discard popup appeared")

def dismiss_post_apply_popup(driver):
    try:
        dismiss_button = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, '//button[@aria-label="Dismiss"]'))
        )
        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'})", dismiss_button)
        dismiss_button.click()
        human_delay(5,10)
        handle_discard_popup(driver)
        print("✅ Dismissed post-application popup")
    except Exception as e:
        print(f"⚠️ No post-application popup found or error dismissing it: {e}")

def uncheck_follow_company_checkbox(driver):
    try:
        checkbox = driver.find_element(By.ID, "follow-company-checkbox")
        is_checked = checkbox.is_selected()
        if is_checked:
            # Click the label instead of the checkbox input
            label = driver.find_element(By.CSS_SELECTOR, 'label[for="follow-company-checkbox"]')
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", label)
            time.sleep(0.5)
            label.click()
            print("✅ Unchecked 'Follow Company'")
        else:
            print("☑️ 'Follow Company' was already unchecked")
    except Exception as e:
        print(f"⚠️ Could not uncheck 'Follow Company': {e}")



def handle_form_step(driver, li_text):
    human_delay(2,4)
    fill_dynamic_form(driver)

    # Check which button appears: Next or Review
    try:
        next_btn = driver.find_element(By.XPATH, '//button[@aria-label="Continue to next step"]')
        driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth', block:'center'});", next_btn)
        next_btn.click()
        print("➡️ Clicked Next for more questions")
        human_delay(2,5)
        return True  # More steps to go

    except:
        try:
            review_btn = driver.find_element(By.XPATH, '//button[@aria-label="Review your application"]')
            driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth', block:'center'});", review_btn)
            review_btn.click()
            print("🔍 Clicked Review")
            human_delay(2,5)

            submit_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, '//button[@aria-label="Submit application"]'))
            )
            uncheck_follow_company_checkbox(driver)
            human_delay(5,10)
            submit_btn.click()
            print("🎯 Application submitted")
            
            data = li_text.split('\n')[:4]
            with open(f'applied_jobs.csv', 'a', encoding='utf-8', newline='') as file:
                writer = csv.writer(file)
                writer.writerow(data)
                print("applied job saved at applied_jobs.csv")
                
            human_delay(15,20)
            dismiss_post_apply_popup(driver)
            return False
        except:
            dismiss_post_apply_popup(driver)
            print("⚠️ No valid form button found")
            return False

def click_each_li(driver, visited):
    print("🔁 Clicking <li> job cards with ID starting with 'ember'...")
    job_cards = driver.find_elements(By.CSS_SELECTOR, 'li[id^="ember"]')
    new_found = False
    
    for li in job_cards:
        try:
            li_text = li.text
            print(f'li text: {li_text}')
            job_id = li.get_attribute("id") or li_text
            if job_id in visited or "Easy Apply" not in li_text:
                continue
            visited.add(job_id)

            scroll_to_element(driver, li)
            ActionChains(driver).move_to_element(li).click().perform()
            print(f"🖱️ Clicked job: {job_id}")
            human_delay(3,6)

            try:
                easy_apply_btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.ID, "jobs-apply-button-id"))
                )
                driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth', block:'center'});", easy_apply_btn)
                human_delay(2,4)
                easy_apply_btn.click()
                print("✅ Clicked Easy Apply button")
                human_delay(2,5)  # Allow popup/modal to load if needed

                next_btn = handle_form_step(driver, li_text)
                while next_btn:
                    next_btn = handle_form_step(driver, li_text)
    
            except Exception:
                print("❌ Easy Apply button not found for this job (probably not eligible)")

            new_found = True
        except Exception as e:
            print(f"⚠️ Could not click job card: {e}")
    return new_found


def click_next_button(driver):
    try:
        next_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, '//button[@aria-label="View next page"]'))
        )
        scroll_to_element(driver, next_btn)
        next_btn.click()
        print("➡️ Clicked Next button")
        human_delay(5,10)
        return True
    except Exception:
        print("❌ No Next button found. Possibly last page.")
        return False

def main():
    driver = setup_driver()
    driver.get("https://www.linkedin.com/jobs/collections/recommended")
    human_delay(5,10)

    visited_jobs = set()
    page_number = 1
    idx = 0
    while True:
        print(f"\n📄 Processing Page #{page_number}")
        wait_for_job_cards(driver)

        has_new = True
        while has_new:
            has_new = click_each_li(driver, visited_jobs)
            driver.execute_script("window.scrollBy(0, 2000);")
            human_delay(2,6)

        if not click_next_button(driver):
            break  # end loop if no next button
        
        den = random.randint(2,6)
        if idx%den == 0:
            print(f"applied to {idx} jobs")
            human_delay(200, 500)
        page_number += 1

    print("✅ Finished visiting all job cards.")
    # driver.quit()

if __name__ == "__main__":
    main()
