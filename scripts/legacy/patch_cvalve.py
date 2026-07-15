import re

with open("jcross_engine_glm/src/lib.rs", "r") as f:
    content = f.read()

target1 = """                let t_v = self.get_candle_tensor(&format!("{}.V", layer_name), &self.candle_device).unwrap();
                let t_s = self.get_candle_tensor(&format!("{}.S", layer_name), &self.candle_device).unwrap();
                let t_u = self.get_candle_tensor(&format!("{}.U", layer_name), &self.candle_device).unwrap();
                
                let temp1 = t_v.matmul(&x_mod).map_err(|e| e.to_string())?;
                let s_col = t_s.reshape((rank as usize, 1)).map_err(|e| e.to_string())?;
                let temp2 = temp1.broadcast_mul(&s_col).map_err(|e| e.to_string())?;
                
                let temp3 = t_u.matmul(&temp2).map_err(|e| e.to_string())?;"""

replacement1 = """                let t_v = self.get_candle_tensor(&format!("{}.V", layer_name), &self.candle_device).unwrap();
                let t_s = self.get_candle_tensor(&format!("{}.S", layer_name), &self.candle_device).unwrap();
                let t_u = self.get_candle_tensor(&format!("{}.U", layer_name), &self.candle_device).unwrap();
                let t_c_valve = self.get_candle_tensor(&format!("{}.c_valve", layer_name), &self.candle_device).unwrap();
                
                let temp1 = t_v.matmul(&x_mod).map_err(|e| e.to_string())?;
                let s_col = t_s.reshape((rank as usize, 1)).map_err(|e| e.to_string())?;
                let temp2 = temp1.broadcast_mul(&s_col).map_err(|e| e.to_string())?;
                let temp_locked = t_c_valve.matmul(&temp2).map_err(|e| e.to_string())?;
                
                let temp3 = t_u.matmul(&temp_locked).map_err(|e| e.to_string())?;"""

target2 = """                let t_v = self.get_candle_tensor(&format!("{}.V", layer_name), &self.candle_device).unwrap();
                let t_s = self.get_candle_tensor(&format!("{}.S", layer_name), &self.candle_device).unwrap();
                let t_u = self.get_candle_tensor(&format!("{}.U", layer_name), &self.candle_device).unwrap();
                
                let temp1 = t_v.matmul(&x_mod).map_err(|e| e.to_string())?; // (r, B)
                let s_col = t_s.reshape((rank as usize, 1)).map_err(|e| e.to_string())?;
                let temp2 = temp1.broadcast_mul(&s_col).map_err(|e| e.to_string())?; // (r, B)
                
                let temp3 = t_u.matmul(&temp2).map_err(|e| e.to_string())?; // (rows, B)"""

replacement2 = """                let t_v = self.get_candle_tensor(&format!("{}.V", layer_name), &self.candle_device).unwrap();
                let t_s = self.get_candle_tensor(&format!("{}.S", layer_name), &self.candle_device).unwrap();
                let t_u = self.get_candle_tensor(&format!("{}.U", layer_name), &self.candle_device).unwrap();
                let t_c_valve = self.get_candle_tensor(&format!("{}.c_valve", layer_name), &self.candle_device).unwrap();
                
                let temp1 = t_v.matmul(&x_mod).map_err(|e| e.to_string())?; // (r, B)
                let s_col = t_s.reshape((rank as usize, 1)).map_err(|e| e.to_string())?;
                let temp2 = temp1.broadcast_mul(&s_col).map_err(|e| e.to_string())?; // (r, B)
                let temp_locked = t_c_valve.matmul(&temp2).map_err(|e| e.to_string())?; // (r, B)
                
                let temp3 = t_u.matmul(&temp_locked).map_err(|e| e.to_string())?; // (rows, B)"""


count1 = content.count(target1)
count2 = content.count(target2)

if count1 > 0:
    content = content.replace(target1, replacement1)
    print("Patched target1")
if count2 > 0:
    content = content.replace(target2, replacement2)
    print("Patched target2")

with open("jcross_engine_glm/src/lib.rs", "w") as f:
    f.write(content)
