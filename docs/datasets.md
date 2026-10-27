# DocuCheck AI — Các bộ dữ liệu

> Tổng hợp và nhận định phục vụ chọn dữ liệu cho project Conquer.
> Nguồn được rà soát ngày 27/10/2026. Cần kiểm tra lại điều khoản và quyền truy cập trước khi tải hoặc đăng dữ liệu.

## 5. Các bộ dữ liệu có thể sử dụng

Các thông tin dưới đây được rà soát từ trang giới thiệu của đơn vị phát hành hoặc trang dataset công khai vào **27/10/2026**. Số lượng phản ánh **bản được mô tả trên nguồn tương ứng**, không mặc định là toàn bộ ảnh đều có thể tải, có cùng loại nhãn hoặc được phép dùng cho mọi mục đích.

### 5.1. MC-OCR 2021 — Ưu tiên số 1 nếu lấy được quyền truy cập

- **Nguồn chính thức:** [RIVF2021 MC-OCR — Dataset](https://www.rivf2021-mc-ocr.vietnlp.com/dataset) và [trang cuộc thi](https://www.rivf2021-mc-ocr.vietnlp.com/).
- **Miền dữ liệu:** biên lai/hóa đơn **tiếng Việt**, được chụp bằng thiết bị di động ở điều kiện thực tế.
- **Quy mô:** website chính thức nêu **hơn 2.000 ảnh** từ hơn 50 người đóng góp, được tổ chức theo các giai đoạn cuộc thi. **Không được hiểu toàn bộ ảnh đều là mẫu train có đủ nhãn KIE**.
- **Nhãn KIE gốc:** `SELLER`, `SELLER_ADDRESS`, `TIMESTAMP`, `TOTAL_COST` (tối đa bốn trường mỗi ảnh).
- **Metadata/annotation:** có thông tin vùng văn bản (`anno_polygons`), nhãn (`anno_labels`), chuỗi ký tự (`anno_texts`) và điểm chất lượng ảnh (`anno_image_quality`) trong phần dữ liệu được mô tả.
- **Điểm mạnh:** đúng ngôn ngữ, đúng loại ảnh chụp, có các trường cốt lõi và chứa nhiều trường hợp mờ/nhăn/lệch.
- **Điểm yếu:** **không có nhãn sẵn đầy đủ** cho tạm tính, giảm giá, thuế, mã hóa đơn hay từng dòng sản phẩm; phần test có thể không công khai đầy đủ ground truth.
- **Điều kiện sử dụng:** trang chính thức ghi **chỉ dùng cho mục đích nghiên cứu**, cần ký thỏa thuận sử dụng dữ liệu và gửi về địa chỉ đăng ký nêu trên trang. Trang Codalab cũ đã đóng đăng ký mới; team phải **xác minh kênh cấp quyền hiện tại**, không giả định tải được ngay.

**Vai trò trong DocuCheck AI:** tập dữ liệu sát bài toán nhất cho phần trích xuất **4 trường lõi** và kiểm tra ảnh chụp hóa đơn tiếng Việt.

### 5.2. CORD-v2 — Nguồn tốt nhất cho cấu trúc tiền và dòng hàng

- **Nguồn phát hành:** [NAVER CLOVA — CORD-v2 trên Hugging Face](https://huggingface.co/datasets/naver-clova-ix/cord-v2); [repository gốc](https://github.com/clovaai/cord).
- **Ngôn ngữ/miền:** chủ yếu hóa đơn bán lẻ, nhà hàng **Indonesia**.
- **Quy mô phát hành:** **1.000 mẫu**; trang Hugging Face hiển thị 3 split, trong đó train 800 (bộ chia phổ biến: 800 train / 100 validation / 100 test).
- **Nhãn nổi bật:** thông tin dòng món hàng (`menu`), tạm tính (`sub_total`), giảm giá, thuế/phí ở một số mẫu, tổng thanh toán (`total`); cấu trúc `gt_parse` hỗ trợ hiểu quan hệ giữa các nhóm trường.
- **Điểm mạnh:** phù hợp để nghiên cứu cách hóa đơn biểu diễn **chi tiết hàng hóa** và **các thành phần của tổng tiền**.
- **Điểm yếu:** khác ngôn ngữ, cách ghi số tiền và kiểu hóa đơn Việt Nam; không thể lấy kết quả trên CORD để tuyên bố hiệu năng trên biên lai tiếng Việt. Theo repository chính thức, một số nhóm nhãn của bản nghiên cứu gốc như `store_info`, `payment_info`, `etc` **đã bị loại khỏi nhãn công bố**.
- **Giấy phép trên nguồn phát hành:** **CC BY 4.0** (cần ghi nguồn và tuân thủ điều kiện giấy phép).

**Vai trò trong DocuCheck AI:** hiểu **vì sao có nhiều số tiền trên một hóa đơn**, phát triển khái niệm kiểm tra tạm tính–giảm giá–thuế–tổng; **không nên dùng làm bộ kiểm thử cuối** cho hóa đơn Việt Nam.

### 5.3. ICDAR 2019 SROIE — Nguồn tham chiếu cho trích xuất trường phổ biến

- **Nguồn:** [SROIE bản mở rộng trên Hugging Face](https://huggingface.co/datasets/jsdnrs/ICDAR2019-SROIE); [trang cuộc thi gốc](https://rrc.cvc.uab.es/?ch=13&com=tasks).
- **Ngôn ngữ/miền:** hóa đơn/biên lai tiếng Anh từ Malaysia.
- **Quy mô cần phân biệt:** một số bản mirror cũ ghi **973 ảnh**; bản `jsdnrs/ICDAR2019-SROIE` ghi **987 ảnh** nhờ bổ sung 14 annotation còn thiếu và sửa metadata. Luôn ghi rõ **phiên bản** khi thống kê.
- **Nhãn:** `company`, `date`, `address`, `total`; kèm từ văn bản và tọa độ vùng (`words`, `bboxes`) ở bản mở rộng.
- **Điểm mạnh:** trường thông tin khá gần với nhóm A của DocuCheck AI; dễ đối chiếu khái niệm trường và bố cục.
- **Điểm yếu:** không phải tiếng Việt, không có sẵn đầy đủ nhãn kiểm tra các thành phần số tiền.
- **Giấy phép:** bản mở rộng trên Hugging Face công bố **CC BY 4.0**. Nếu lấy một mirror khác, cần kiểm tra lại thông tin giấy phép và nguồn dữ liệu.

**Vai trò trong DocuCheck AI:** nguồn bổ sung để kiểm tra tính đa dạng bố cục, **không thay thế** dữ liệu tiếng Việt.

### 5.4. Vietnamese Bill Extraction VLM Dataset — Nguồn mở rộng có chọn lọc

- **Nguồn:** [minhduc168/dataset-origin-vlm-extract-bill trên Hugging Face](https://huggingface.co/datasets/minhduc168/dataset-origin-vlm-extract-bill).
- **Ngôn ngữ:** tiếng Việt.
- **Quy mô trang dataset:** **982 bản ghi** trong một split `train` vào thời điểm kiểm tra.
- **Nhãn thấy trên bản xem trước:** ảnh đi cùng `master_data` gồm các trường như `ten_dich_vu`, `so_luong`, `don_vi_tinh`, `don_gia`, `thanh_tien`. Nhiều mẫu xem trước thuộc **hóa đơn/dịch vụ y tế**, không giống biên lai cửa hàng bán lẻ thông thường.
- **Điểm mạnh:** có dữ liệu tiếng Việt về **các dòng dịch vụ/sản phẩm và số tiền**.
- **Giới hạn:** chưa thấy trên phần xem trước một bộ nhãn vị trí đầy đủ tương ứng với 4 trường lõi; **không nên coi là dataset KIE biên lai bán lẻ có bbox sẵn**. Dataset card và dữ liệu xem trước có cách mô tả cấu trúc chưa hoàn toàn đồng nhất, nên cần kiểm tra bản ghi thật trước khi sử dụng.
- **Giấy phép hiển thị trên Hugging Face:** `MIT`. Dù vậy, team vẫn phải kiểm tra **nguồn gốc, quyền đối với ảnh và rủi ro dữ liệu cá nhân/nhạy cảm**, đặc biệt nếu có chứng từ y tế; giấy phép trên trang không tự chứng minh rằng mọi dữ liệu cá nhân đều đã được cho phép sử dụng lại.

**Vai trò trong DocuCheck AI:** **tùy chọn**, chỉ xem xét nếu team thật sự muốn mở rộng tới bảng dòng hàng. **Không phải lựa chọn cốt lõi** cho bản đầu.

### 5.5. Dữ liệu tự xây dựng — Phần bắt buộc nếu muốn kiểm tra sâu

Team sẽ khó hoàn thành đúng ý tưởng DocuCheck AI nếu chỉ ghép các nguồn công khai ở trên. Cần có **một tập hóa đơn tiếng Việt do team gán nhãn theo định nghĩa của chính sản phẩm**, đặc biệt để kiểm tra các trường mới và trạng thái cảnh báo.

**Loại mẫu nên có:**

- Hóa đơn đơn giản chỉ có nơi bán, ngày, tổng tiền.
- Hóa đơn có tạm tính và giảm giá.
- Hóa đơn có thuế, phí dịch vụ, tiền khách đưa, tiền thối lại.
- Hóa đơn bị nhòe, nghiêng, ánh sáng yếu hoặc có một trường không đọc được.
- Hóa đơn có **thiếu trường thật sự** để kiểm thử khả năng không tự điền bừa.
- Các mẫu đối chiếu giả lập mà tổng tiền **cố ý không nhất quán**, phân biệt rõ dữ liệu được tạo cho kiểm tra cảnh báo với chứng từ thật.

**Hai nguồn bổ sung có thể dùng:** (1) hóa đơn mẫu **tự thiết kế**, không sử dụng logo/thông tin thật theo cách gây hiểu nhầm; (2) ảnh thực tế **được chủ sở hữu cho phép sử dụng**, đã loại bỏ thông tin không cần thiết.

**Quy mô đề nghị chỉ để hình dung:** bắt đầu một bộ nhỏ khoảng **100–200 ảnh được rà soát kỹ**, rồi mở rộng lên khoảng **200–400 ảnh** nếu nguồn lực cho phép. **Đây là mục tiêu tự đề xuất, không phải con số có sẵn hay mức bảo đảm đủ để huấn luyện tốt.**

**Tối thiểu mỗi mẫu nên có:**

| Thành phần nhãn | Vì sao cần? |
|---|---|
| Loại tài liệu và nguồn mẫu | Biết dữ liệu từ đâu và quyền sử dụng |
| Giá trị đúng của từng trường mục tiêu | Xác định AI có trích xuất đúng không |
| Vị trí trên ảnh (nếu có thể) | Cho phép hiển thị bằng chứng và kiểm tra lỗi |
| Trạng thái `present` / `absent` / `unreadable` | Không đánh đồng thiếu trường với OCR thất bại |
| Các thành phần tiền đủ để đối chiếu | Làm cơ sở kiểm tra số học đáng tin cậy |
| Kết luận cảnh báo đã được rà soát | Đánh giá khả năng phát hiện sai lệch, hạn chế cảnh báo oan |

**Nguyên tắc quan trọng:** không chia ngẫu nhiên nhiều ảnh của cùng một hóa đơn hoặc cùng một mẫu template sang cả train và test. Dữ liệu đánh giá nên chứa **mẫu hóa đơn/cửa hàng chưa xuất hiện ở phần phát triển** để phản ánh khả năng xử lý bố cục mới. Với dữ liệu giả lập, cần đảm bảo tập đánh giá độc lập không chỉ là bản đổi chữ/số của template đã dùng trước đó.

---

---

## 6. So sánh nhanh: mỗi bộ dữ liệu phục vụ phần nào?

| Bộ dữ liệu | Tiếng Việt | Nơi bán/ngày/tổng | Tạm tính/thuế/giảm giá | Dòng sản phẩm | Vai trò đề xuất |
|---|:---:|:---:|:---:|:---:|---|
| **MC-OCR** | ✅ | ✅ (4 trường lõi, có thể thiếu trên từng ảnh) | ❌ Không có nhãn chuẩn tương ứng | ❌ | **Ưu tiên cho bài toán lõi** nếu được cấp quyền |
| **CORD-v2** | ❌ | ⚠️ Không đầy đủ trường nơi bán | ✅ Có trên một phần mẫu | ✅ | Hiểu cấu trúc hóa đơn và nhóm số tiền |
| **SROIE (bản mở rộng)** | ❌ | ✅ (company/date/address/total) | ❌ | ❌ | Dữ liệu tham chiếu để so sánh trường |
| **Vietnamese Bill VLM** | ✅ | ⚠️ Không phải trọng tâm nhãn công bố | ⚠️ Một số trường tiền theo dòng | ✅ Chủ yếu line items | Nguồn tùy chọn, cần audit kỹ |
| **Dữ liệu của team** | ✅ | ✅ nếu team gán nhãn | ✅ nếu team gán nhãn | Tùy phạm vi | **Bắt buộc** để chứng minh đúng trải nghiệm muốn xây |

**Chú thích:** ✅ chỉ có nghĩa là nguồn đó hỗ trợ nhóm thông tin tương ứng theo tài liệu công bố; **không** có nghĩa mọi ảnh đều chứa nhãn hoặc mọi mẫu đều có thể truy cập/tái sử dụng. ⚠️ nghĩa là chỉ phù hợp một phần và phải rà soát trước.

### Khoảng trống dữ liệu cần nhận ra ngay

1. **Khoảng trống tiếng Việt + nhãn đủ cho đối chiếu số tiền:** MC-OCR không có sẵn toàn bộ trường; CORD có nhiều trường nhưng khác miền ngôn ngữ.
2. **Khoảng trống bằng chứng trên ảnh:** dữ liệu `giá trị cuối` không luôn có vị trí ảnh tương ứng để highlight chính xác.
3. **Khoảng trống nhãn “không đọc được”:** tập dữ liệu thông thường không nhất thiết phân biệt thiếu trường và ảnh mờ khiến không đọc được.
4. **Khoảng trống dữ liệu cho validation:** muốn đánh giá cảnh báo đúng/sai thì phải có ground truth về các thành phần số học và trường hợp không nhất quán, không chỉ text OCR.
5. **Khoảng trống quyền sử dụng:** nguồn công khai và nguồn cho phép nghiên cứu **không đồng nghĩa** được phép công bố lại toàn bộ ảnh hay dùng trong demo thương mại.

---

---

## 7. Định hướng chọn dữ liệu cho DocuCheck AI

Không cần ôm tất cả dataset ngay từ đầu. Nên áp dụng thứ tự ưu tiên theo **ý nghĩa đối với project**, không theo quy mô ảnh:

**Ưu tiên A — Nền tảng hóa đơn tiếng Việt:** kiểm tra khả năng truy cập hợp lệ **MC-OCR**; song song chuẩn bị một bộ hóa đơn tiếng Việt do team tự kiểm soát, có nhãn 4 trường lõi.  
**Ưu tiên B — Thông tin tiền và đối chiếu:** dùng **CORD-v2 như nguồn tham khảo cấu trúc**, sau đó thu thập/gán nhãn **các trường tiền trên hóa đơn tiếng Việt** tương ứng với loại chứng từ muốn kiểm tra.  
**Ưu tiên C — Mở rộng khi thật sự cần:** **SROIE** giúp tham khảo trích xuất 4 trường phổ biến; **Vietnamese Bill VLM** phù hợp hơn với dòng hàng/dịch vụ, nhưng cần kiểm tra quyền sử dụng và độ tương thích nhãn trước.

### Vì sao không nên trộn tất cả ảnh thành một tập chung?

Vì các nguồn có **ngôn ngữ, nhãn, loại chứng từ và điều kiện cấp phép khác nhau**. Một trường `total` ở tập này có thể không hoàn toàn tương đương `cashprice`, `total_price` hay `TOTAL_COST` ở tập khác. Team phải thống nhất định nghĩa trường và xem dữ liệu nào thực sự đo đúng bài toán mình đặt ra.

---

---

## 9. Nguồn tham khảo và liên kết dữ liệu

1. **MC-OCR 2021 — Dataset (chính thức):** https://www.rivf2021-mc-ocr.vietnlp.com/dataset  
   **Giới thiệu thử thách:** https://www.rivf2021-mc-ocr.vietnlp.com/  
   **Bài mô tả challenge:** https://people.cs.umu.se/sonvx/files/MCOCR_Preprint.pdf
2. **CORD-v2 (nhà phát hành):** https://huggingface.co/datasets/naver-clova-ix/cord-v2  
   **Repository / thông tin giấy phép:** https://github.com/clovaai/cord
3. **ICDAR 2019 SROIE (bản mở rộng 987 mẫu):** https://huggingface.co/datasets/jsdnrs/ICDAR2019-SROIE  
   **Cuộc thi gốc:** https://rrc.cvc.uab.es/?ch=13&com=tasks
4. **Vietnamese Bill Extraction VLM Dataset:** https://huggingface.co/datasets/minhduc168/dataset-origin-vlm-extract-bill
5. **Tài liệu tham khảo bổ sung về dữ liệu hóa đơn tiếng Việt:** [UIT-MLReceipts — REV Journal](https://www.rev-jec.org/index.php/rev-jec/article/view/330) (tập trung vào phát hiện/nhận dạng text; không coi mặc nhiên là bộ nhãn KIE đầy đủ).

> **Lưu ý nguồn:** Tài liệu dùng trang gốc và dataset card làm bằng chứng mô tả, **chưa tải toàn bộ dữ liệu để audit**. Quyền truy cập, phiên bản, nhãn thực tế và điều khoản khi tải cần được xác nhận lại trước khi team sử dụng hoặc công bố bất kỳ tập ảnh nào.

---

**Kết luận:** Ý tưởng DocuCheck AI mạnh nhất khi được định vị là **“trích xuất dữ liệu có bằng chứng + cảnh báo có điều kiện + người dùng xác nhận”** cho một phạm vi chứng từ hẹp. Về dữ liệu, **MC-OCR (nếu truy cập hợp lệ) + tập tiếng Việt tự gán nhãn** là trục chính; **CORD-v2** giúp xây dựng hiểu biết về nhóm trường số tiền; các nguồn còn lại đóng vai trò bổ sung. Cần chốt ranh giới này trước khi team chia việc hoặc chọn mô hình.

---

## Kết luận cho team

- **Ưu tiên:** MC-OCR (nếu nhận quyền sử dụng) cùng bộ biên lai tiếng Việt do team được phép thu thập và tự gán nhãn.
- **Tham khảo cấu trúc trường số tiền:** CORD-v2.
- **Bổ sung có chọn lọc:** SROIE và Vietnamese Bill VLM sau khi xem xét nhãn và điều kiện sử dụng.
- Không công khai ảnh chứng từ thật, thông tin cá nhân, hoặc dataset hạn chế quyền phân phối trên GitHub public.

Xem định nghĩa bài toán trong [docs/idea.md](idea.md).
