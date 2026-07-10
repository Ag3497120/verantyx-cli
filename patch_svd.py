import re

with open("jcross_engine_glm/src/lib.rs", "r") as f:
    content = f.read()

# Fix project_vector
target1 = """            TensorType::SVDLossless { rows, cols, rank } => {
                let x_t = Tensor::from_slice(input_slice, (cols as usize, 1), &self.candle_device).map_err(|e| e.to_string())?;
                let x_t_f16 = x_t.to_dtype(DType::F16).map_err(|e| e.to_string())?;
                
                let t_v = self.get_candle_tensor(&format!("{}.V", layer_name), &self.candle_device).unwrap();
                let t_s = self.get_candle_tensor(&format!("{}.S", layer_name), &self.candle_device).unwrap();
                let t_u = self.get_candle_tensor(&format!("{}.U", layer_name), &self.candle_device).unwrap();
                
                // temp = V^T * x (v is saved as r x n, which is V^T)
                let temp1 = t_v.matmul(&x_t_f16).map_err(|e| e.to_string())?;
                // s is shape (r,), we need to broadcast mul or use diag. 
                // Since temp1 is (r, 1), s is (r,). We reshape s to (r, 1) and elementwise multiply.
                let s_col = t_s.reshape((rank as usize, 1)).map_err(|e| e.to_string())?;
                let temp2 = temp1.broadcast_mul(&s_col).map_err(|e| e.to_string())?;
                
                // U is (m, r). U * temp2
                let temp3 = t_u.matmul(&temp2).map_err(|e| e.to_string())?;
                
                let out_f32 = temp3.to_dtype(DType::F32).map_err(|e| e.to_string())?;"""

replacement1 = """            TensorType::SVDLossless { rows, cols, rank } => {
                let x_t = Tensor::from_slice(input_slice, (cols as usize, 1), &self.candle_device).map_err(|e| e.to_string())?;
                let x_t_f16 = x_t.to_dtype(DType::F16).map_err(|e| e.to_string())?;
                
                let t_mod_x = self.get_candle_tensor(&format!("{}.mod_x", layer_name), &self.candle_device).unwrap();
                let t_mod_x_f16 = t_mod_x.reshape((cols as usize, 1)).unwrap();
                let x_mod = x_t_f16.broadcast_mul(&t_mod_x_f16).unwrap();

                let t_v = self.get_candle_tensor(&format!("{}.V", layer_name), &self.candle_device).unwrap();
                let t_s = self.get_candle_tensor(&format!("{}.S", layer_name), &self.candle_device).unwrap();
                let t_u = self.get_candle_tensor(&format!("{}.U", layer_name), &self.candle_device).unwrap();
                
                let temp1 = t_v.matmul(&x_mod).map_err(|e| e.to_string())?;
                let s_col = t_s.reshape((rank as usize, 1)).map_err(|e| e.to_string())?;
                let temp2 = temp1.broadcast_mul(&s_col).map_err(|e| e.to_string())?;
                
                let temp3 = t_u.matmul(&temp2).map_err(|e| e.to_string())?;
                
                let t_mod_y = self.get_candle_tensor(&format!("{}.mod_y", layer_name), &self.candle_device).unwrap();
                let t_mod_y_f16 = t_mod_y.reshape((rows as usize, 1)).unwrap();
                let temp4 = temp3.broadcast_add(&t_mod_y_f16).unwrap();

                let out_f32 = temp4.to_dtype(DType::F32).map_err(|e| e.to_string())?;"""

# Fix project_matrix
target2 = """            TensorType::SVDLossless { rows, cols, rank } => {
                let x_t = Tensor::from_slice(input_slice, (b, cols as usize), &self.candle_device).map_err(|e| e.to_string())?;
                let x_t_f16 = x_t.to_dtype(DType::F16).map_err(|e| e.to_string())?;
                let x_t_f16_t = x_t_f16.t().map_err(|e| e.to_string())?; // (cols, B)
                
                let t_v = self.get_candle_tensor(&format!("{}.V", layer_name), &self.candle_device).unwrap();
                let t_s = self.get_candle_tensor(&format!("{}.S", layer_name), &self.candle_device).unwrap();
                let t_u = self.get_candle_tensor(&format!("{}.U", layer_name), &self.candle_device).unwrap();
                
                // temp1 = V^T * x_t_f16_t. V^T is stored as V with shape (r, cols).
                let temp1 = t_v.matmul(&x_t_f16_t).map_err(|e| e.to_string())?; // (r, B)
                let s_col = t_s.reshape((rank as usize, 1)).map_err(|e| e.to_string())?;
                let temp2 = temp1.broadcast_mul(&s_col).map_err(|e| e.to_string())?; // (r, B)
                
                // U is (m, r). U * temp2 -> (m, B)
                let temp3 = t_u.matmul(&temp2).map_err(|e| e.to_string())?;
                
                let out_f32 = temp3.to_dtype(DType::F32).map_err(|e| e.to_string())?;"""

replacement2 = """            TensorType::SVDLossless { rows, cols, rank } => {
                let x_t = Tensor::from_slice(input_slice, (b, cols as usize), &self.candle_device).map_err(|e| e.to_string())?;
                let x_t_f16 = x_t.to_dtype(DType::F16).map_err(|e| e.to_string())?;
                let x_t_f16_t = x_t_f16.t().map_err(|e| e.to_string())?; // (cols, B)
                
                let t_mod_x = self.get_candle_tensor(&format!("{}.mod_x", layer_name), &self.candle_device).unwrap();
                let t_mod_x_f16 = t_mod_x.reshape((cols as usize, 1)).unwrap();
                let x_mod = x_t_f16_t.broadcast_mul(&t_mod_x_f16).unwrap(); // (cols, 1) broadcast over (cols, B)

                let t_v = self.get_candle_tensor(&format!("{}.V", layer_name), &self.candle_device).unwrap();
                let t_s = self.get_candle_tensor(&format!("{}.S", layer_name), &self.candle_device).unwrap();
                let t_u = self.get_candle_tensor(&format!("{}.U", layer_name), &self.candle_device).unwrap();
                
                let temp1 = t_v.matmul(&x_mod).map_err(|e| e.to_string())?; // (r, B)
                let s_col = t_s.reshape((rank as usize, 1)).map_err(|e| e.to_string())?;
                let temp2 = temp1.broadcast_mul(&s_col).map_err(|e| e.to_string())?; // (r, B)
                
                let temp3 = t_u.matmul(&temp2).map_err(|e| e.to_string())?; // (rows, B)
                
                let t_mod_y = self.get_candle_tensor(&format!("{}.mod_y", layer_name), &self.candle_device).unwrap();
                let t_mod_y_f16 = t_mod_y.reshape((rows as usize, 1)).unwrap();
                let temp4 = temp3.broadcast_add(&t_mod_y_f16).unwrap();

                let out_f32 = temp4.to_dtype(DType::F32).map_err(|e| e.to_string())?;"""

if target1 in content:
    content = content.replace(target1, replacement1)
    print("Patched target1")
if target2 in content:
    content = content.replace(target2, replacement2)
    print("Patched target2")

with open("jcross_engine_glm/src/lib.rs", "w") as f:
    f.write(content)
