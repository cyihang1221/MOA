function   x = bigEndianBytesToSingle(x)
%by: Magnus Åberg

x = typecast(uint8(x),'uint32');
x = typecast(swapbytes(x),'single');