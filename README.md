要先上https://github.com/AI-FREE-Team/Traditional-Chinese-Handwriting-Dataset 將完整資料集下載下來，得到cleaned_data

```bash
python gen_handwriting_chinese_price.py --char_dir "handwritting_data_all/cleaned_data" --bg_image "invoice_train_data.jpg" --output_dir "" --count 100
```
<img width="772" height="79" alt="image" src="https://github.com/user-attachments/assets/97df345f-2a5e-4c01-8160-cd032ca93d70" />
<img width="770" height="84" alt="image" src="https://github.com/user-attachments/assets/73c02c21-84da-4c45-ac5e-7ed807983e11" />
<img width="769" height="78" alt="image" src="https://github.com/user-attachments/assets/44e225ef-236a-417c-9dcd-d08ed9dda936" />

```bash
python gen_casia_company.py --casia_dir "" --bg_image "invoice_train_data.jpg" --company_list "all_company_name_for_invoice_synthetic.txt"  --output_dir ""
```
<img width="1662" height="139" alt="image" src="https://github.com/user-attachments/assets/a7820561-6374-4471-88ec-cc240ecdb030" />
<img width="1695" height="133" alt="image" src="https://github.com/user-attachments/assets/d8251535-17f7-4d22-b591-645b00d95d04" />
<img width="1739" height="137" alt="image" src="https://github.com/user-attachments/assets/8b61ca29-b1bf-467b-8dec-407711a2ac10" />

```bash
python gen_handwriting_company.py --char_data_dir "handwritting_data_all/cleaned_data" --bg_image "invoice_train_data.jpg" --company_list "all_company_name_for_invoice_synthetic.txt" --output_dir ""
```
<img width="1562" height="140" alt="image" src="https://github.com/user-attachments/assets/6def4698-fb04-40ca-aff1-17f832cfdade" />
<img width="1726" height="174" alt="image" src="https://github.com/user-attachments/assets/f46bbeed-ee41-4e7a-8263-1a64d3126237" />
<img width="1765" height="119" alt="image" src="https://github.com/user-attachments/assets/51f043c4-e203-4682-9c59-ffd000860358" />


<img width="1516" height="120" alt="image" src="https://github.com/user-attachments/assets/d3dfcbe7-2743-4177-8631-71b4985750ca" />
<img width="1525" height="126" alt="image" src="https://github.com/user-attachments/assets/8f914450-bb70-42a6-8153-61c1ce0d2bfd" />
<img width="1523" height="107" alt="image" src="https://github.com/user-attachments/assets/523f79e4-d2ea-4619-ac0a-618fa2676197" />






