// 图片解密模块 - 用于解密 JMComic 的分片图片
use anyhow::{Context, Result};
use image::{DynamicImage, GenericImageView, ImageBuffer, Pixel};
use md5;
use std::path::Path;

/// JMComic 魔法常量
const SCRAMBLE_268850: u32 = 268850;
const SCRAMBLE_421926: u32 = 421926;

/// 从 URL 或文件路径提取文件名（不含扩展名）
fn extract_filename(url_or_path: &str) -> String {
    let path = Path::new(url_or_path);
    
    // 获取文件名
    let filename = path
        .file_name()
        .and_then(|f| f.to_str())
        .unwrap_or("");
    
    // 移除扩展名
    Path::new(filename)
        .file_stem()
        .and_then(|f| f.to_str())
        .unwrap_or(filename)
        .to_string()
}

/// 从 URL 提取 aid（相册ID）
/// URL 格式: https://cdn-msp.jmapiproxy2.cc/media/photos/485053/00032.webp
fn extract_aid_from_url(url: &str) -> Option<u32> {
    // 寻找 /photos/ 后面的数字
    if let Some(photos_pos) = url.find("/photos/") {
        let after_photos = &url[photos_pos + 8..]; // 跳过 "/photos/"
        if let Some(slash_pos) = after_photos.find('/') {
            let aid_str = &after_photos[..slash_pos];
            return aid_str.parse::<u32>().ok();
        }
    }
    None
}

/// 计算图片的分割数量
/// 
/// # Arguments
/// * `scramble_id` - 解密标识ID
/// * `aid` - 相册ID（album ID）
/// * `filename` - 图片文件名（不含扩展名）
/// 
/// # Returns
/// 分割数量，0 表示不需要解密
pub fn calculate_split_num(scramble_id: u32, aid: u32, filename: &str) -> u32 {
    // 不需要解密
    if aid < scramble_id {
        return 0;
    }
    
    // 固定分割为 10
    if aid < SCRAMBLE_268850 {
        return 10;
    }
    
    // 根据 MD5 hash 计算分割数
    let x = if aid < SCRAMBLE_421926 { 10 } else { 8 };
    
    // 拼接字符串: aid + filename
    let s = format!("{}{}", aid, filename);
    
    // 计算 MD5
    let digest = md5::compute(s.as_bytes());
    let hash_hex = format!("{:x}", digest);
    
    // 获取最后一个字符的 ASCII 值
    if let Some(last_char) = hash_hex.chars().last() {
        let ascii_val = last_char as u32;
        let num = (ascii_val % x) * 2 + 2;
        return num;
    }
    
    0
}

/// 解密并保存图片（支持格式转换）
/// 
/// # Arguments
/// * `img_path` - 目标图片路径（可能包含需要转换的格式）
/// * `scramble_id` - 解密标识ID
/// * `aid` - 相册ID
/// * `url` - 原始 URL（用于提取 filename 和原始格式）
pub fn descramble_image(
    img_path: &str,
    scramble_id: u32,
    aid: u32,
    url: &str,
) -> Result<()> {
    // 提取文件名（不含扩展名）
    let filename = extract_filename(url);
    
    // 计算分割数
    let num = calculate_split_num(scramble_id, aid, &filename);
    
    // 检查是否需要格式转换
    let url_ext = extract_url_extension(url);
    let target_ext = Path::new(img_path)
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_lowercase();
    
    let needs_conversion = !url_ext.is_empty() 
        && !target_ext.is_empty() 
        && url_ext != target_ext;
    
    // 如果需要格式转换，采用两阶段处理
    if needs_conversion {
        // 阶段1：将文件临时重命名为原始格式
        let temp_path = format!("{}.orig{}", img_path, if !url_ext.is_empty() { format!(".{}", url_ext) } else { String::new() });
        
        std::fs::rename(img_path, &temp_path)
            .with_context(|| format!("Failed to rename to temp file: {} -> {}", img_path, temp_path))?;
        
        // 阶段2：读取、解密、转换、保存
        let result = process_and_convert(&temp_path, img_path, num);
        
        // 清理临时文件
        let _ = std::fs::remove_file(&temp_path);
        
        return result;
    }
    
    // 无需格式转换，直接处理
    let img = image::open(img_path)
        .with_context(|| format!("Failed to open image: {}", img_path))?;
    
    // 不需要解密
    if num == 0 {
        return Ok(());
    }
    
    // 解密并保存
    let decoded_img = descramble_image_impl(&img, num)?;
    decoded_img
        .save(img_path)
        .with_context(|| format!("Failed to save decoded image: {}", img_path))?;
    
    Ok(())
}

/// 处理图片并转换格式（从临时文件到目标文件）
fn process_and_convert(temp_path: &str, target_path: &str, num: u32) -> Result<()> {
    // 读取临时文件
    let img = image::open(temp_path)
        .with_context(|| format!("Failed to open temp image: {}", temp_path))?;
    
    // 解密（如果需要）
    let final_img = if num == 0 {
        img
    } else {
        descramble_image_impl(&img, num)?
    };
    
    // 保存到目标路径（自动转换格式）
    final_img
        .save(target_path)
        .with_context(|| format!("Failed to save and convert image: {}", target_path))?;
    
    Ok(())
}

/// 从 URL 提取原始文件扩展名
fn extract_url_extension(url: &str) -> String {
    if let Some(last_slash) = url.rfind('/') {
        let filename_part = &url[last_slash + 1..];
        // 移除查询参数
        let filename_part = if let Some(question_mark) = filename_part.find('?') {
            &filename_part[..question_mark]
        } else {
            filename_part
        };
        
        // 提取扩展名
        if let Some(dot_pos) = filename_part.rfind('.') {
            return filename_part[dot_pos + 1..].to_lowercase();
        }
    }
    String::new()
}

/// 实际的图片解密逻辑
fn descramble_image_impl(img: &DynamicImage, num: u32) -> Result<DynamicImage> {
    let (w, h) = img.dimensions();
    
    // 创建新的解密图片
    let mut img_decode = ImageBuffer::new(w, h);
    
    let num = num as u32;
    let over = h % num;
    
    for i in 0..num {
        let move_height = h / num;
        let y_src = h - (move_height * (i + 1)) - over;
        let mut y_dst = move_height * i;
        let mut current_move = move_height;
        
        if i == 0 {
            current_move += over;
        } else {
            y_dst += over;
        }
        
        // 裁剪源图片的一个条纹
        let stripe = img.crop_imm(0, y_src, w, current_move);
        
        // 粘贴到目标位置
        for (x, y, pixel) in stripe.pixels() {
            let target_y = y_dst + y;
            if target_y < h {
                img_decode.put_pixel(x, target_y, pixel.to_rgb());
            }
        }
    }
    
    Ok(DynamicImage::ImageRgb8(img_decode))
}

/// 从 URL 自动提取 aid 并解密图片
pub fn descramble_image_auto(
    img_path: &str,
    scramble_id: u32,
    url: &str,
) -> Result<()> {
    // 从 URL 提取 aid
    let aid = extract_aid_from_url(url)
        .with_context(|| format!("Failed to extract aid from URL: {}", url))?;
    
    descramble_image(img_path, scramble_id, aid, url)
}

#[cfg(test)]
mod tests {
    use super::*;
    
    #[test]
    fn test_calculate_split_num() {
        // aid < scramble_id，不需要解密
        assert_eq!(calculate_split_num(220980, 200000, "test"), 0);
        
        // aid < 268850，固定 10
        assert_eq!(calculate_split_num(220980, 250000, "test"), 10);
        
        // aid >= 268850，根据 MD5 计算
        let num = calculate_split_num(220980, 485053, "00032");
        assert!(num >= 2 && num <= 20);
    }
    
    #[test]
    fn test_extract_aid_from_url() {
        let url = "https://cdn-msp.jmapiproxy2.cc/media/photos/485053/00032.webp";
        assert_eq!(extract_aid_from_url(url), Some(485053));
        
        let url2 = "https://cdn-msp2.jmapiproxy2.cc/media/photos/547798/00080.webp";
        assert_eq!(extract_aid_from_url(url2), Some(547798));
    }
    
    #[test]
    fn test_extract_filename() {
        let url = "https://cdn-msp.jmapiproxy2.cc/media/photos/485053/00032.webp";
        assert_eq!(extract_filename(url), "00032");
        
        let path = "/path/to/image.jpg";
        assert_eq!(extract_filename(path), "image");
    }
}

