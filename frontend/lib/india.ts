/** Indian states/UTs accepted by the backend (pricing_service.VALID_INDIAN_STATE_CODES). */
export const INDIAN_STATES: { code: string; name: string }[] = [
  ["AN", "Andaman and Nicobar Islands"], ["AP", "Andhra Pradesh"], ["AR", "Arunachal Pradesh"],
  ["AS", "Assam"], ["BR", "Bihar"], ["CH", "Chandigarh"], ["CG", "Chhattisgarh"],
  ["DN", "Dadra and Nagar Haveli and Daman and Diu"], ["DL", "Delhi"], ["GA", "Goa"],
  ["GJ", "Gujarat"], ["HR", "Haryana"], ["HP", "Himachal Pradesh"], ["JK", "Jammu and Kashmir"],
  ["JH", "Jharkhand"], ["KA", "Karnataka"], ["KL", "Kerala"], ["LA", "Ladakh"], ["LD", "Lakshadweep"],
  ["MP", "Madhya Pradesh"], ["MH", "Maharashtra"], ["MN", "Manipur"], ["ML", "Meghalaya"],
  ["MZ", "Mizoram"], ["NL", "Nagaland"], ["OD", "Odisha"], ["PY", "Puducherry"], ["PB", "Punjab"],
  ["RJ", "Rajasthan"], ["SK", "Sikkim"], ["TN", "Tamil Nadu"], ["TS", "Telangana"], ["TR", "Tripura"],
  ["UP", "Uttar Pradesh"], ["UK", "Uttarakhand"], ["WB", "West Bengal"],
].map(([code, name]) => ({ code, name }));

export const GSTIN_PATTERN = /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;
