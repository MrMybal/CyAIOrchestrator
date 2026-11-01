Add-Type -AssemblyName System.Drawing
$src = [System.Drawing.Bitmap]::FromFile((Join-Path $PSScriptRoot '../assets/branding/cyai-orchestrator-logo-v1.png'))
$dst = New-Object System.Drawing.Bitmap($src.Width, $src.Height)
for ($y=0; $y -lt $src.Height; $y++) {
    $left=-1; $right=-1
    for ($x=0; $x -lt $src.Width; $x++) {
        $c=$src.GetPixel($x,$y)
        if (($c.B-$c.G) -gt 35 -and ($c.R-$c.G) -gt 15) {
            if ($left -lt 0) {$left=$x}; $right=$x
        }
    }
    if ($left -ge 0) {
        for ($x=$left; $x -le $right; $x++) {$dst.SetPixel($x,$y,$src.GetPixel($x,$y))}
    }
}
$base=Join-Path $PSScriptRoot '../cyai/web/cyai-logo'
$dst.Save($base+'.png',[System.Drawing.Imaging.ImageFormat]::Png)
$sizes=@(16,20,24,32,40,48,64,128,256)
$blobs=New-Object System.Collections.Generic.List[byte[]]
foreach ($size in $sizes) {
    $small=New-Object System.Drawing.Bitmap($size,$size)
    $g=[System.Drawing.Graphics]::FromImage($small)
    $g.InterpolationMode=[System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.PixelOffsetMode=[System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $g.DrawImage($dst,0,0,$size,$size)
    $ms=New-Object System.IO.MemoryStream
    $small.Save($ms,[System.Drawing.Imaging.ImageFormat]::Png)
    $blobs.Add($ms.ToArray())
    $ms.Dispose(); $g.Dispose(); $small.Dispose()
}
$writer=New-Object System.IO.BinaryWriter([System.IO.File]::Create($base+'.ico'))
$writer.Write([uint16]0); $writer.Write([uint16]1); $writer.Write([uint16]$sizes.Count)
$offset=6+16*$sizes.Count
for ($i=0; $i -lt $sizes.Count; $i++) {
    $dimension=if ($sizes[$i] -eq 256) {0} else {$sizes[$i]}
    $writer.Write([byte]$dimension); $writer.Write([byte]$dimension)
    $writer.Write([byte]0); $writer.Write([byte]0)
    $writer.Write([uint16]1); $writer.Write([uint16]32)
    $writer.Write([int]$blobs[$i].Length); $writer.Write([int]$offset)
    $offset+=$blobs[$i].Length
}
foreach ($blob in $blobs) {$writer.Write($blob)}
$writer.Dispose()
Write-Output "Alpha corner=$($dst.GetPixel(0,0).A), center=$($dst.GetPixel(600,600).A); ICO sizes=$sizes"
$dst.Dispose(); $src.Dispose()
