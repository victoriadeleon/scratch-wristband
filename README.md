### Multimodal Wristband for Real-Time Scratch Detection in Patients with Chronic Itch

### Summary
Eczema, or atopic dermatitis, is a chronic inflammatory skin condition characterized by pruritus (itch), which triggers a compulsive urge to scratch. This scratching leads to skin damage, inflammation, and increased infection risk. Current methods for patient assessment, primarily visual inspection and self-reporting, are hindered by subjectivity and limited specificity, failing to accurately quantify the frequency, intensity, and duration of itching episodes.

To address this challenge, we are developing a wearable wristband at the Robotic Caregiving and Human Interaction Lab at Carnegie Mellon University. This innovative device enables real-time, objective detection and quantification of scratching behaviors in chronic itch patients, aiming to advance eczema treatment and improve patient care. It integrates acceleration sensing to capture broad movements, such as arm motions and vibrations, with capacitive sensing to detect tendon activity through direct contact with the wrist. These complementary measurements provide a precise and comprehensive representation of scratching behavior, with the ultimate goal of distinguishing normal activities, like waving or touching objects, from the act of scratching.

The device employs a SEEED Studio ESP32C3 board to transmit data over Wi-Fi using the UDP protocol, enabling real-time data collection and analysis. Data will be gathered from multiple test subjects to train a machine learning algorithm, ensuring reliable and accurate scratch detection. Once the algorithm is fully developed, all functionality will be integrated into a user-friendly mobile app. This app will empower patients and caregivers to monitor scratching behaviors, track progress over time, and receive real-time feedback, making the solution both accessible and practical for everyday use.

In this repository you'll find the software and hardware files fundamental to the device's development process.

![image](https://github.com/user-attachments/assets/c004416c-9262-4a2b-a296-18570cefe2b0)
