function x = decodeBase64(str,endian,precision)
% x = decodeBase64(str,endian,precision)
% x - result in double
% endian - [little | big]
% precision - [32 | 64]
%
% Magnus Åberg 2010-06-22

y=base64decode(str);

switch lower(endian)
   case { 'big', 'network' }
      switch precision
         case '32'
            x = double(bigEndianBytesToSingle(y));
         case '64'
            x = bigEndianBytesToDouble(y);
         otherwise
            error('unknown precision')
      end
      
   case 'little'
      switch precision
         case '32'
            x = double(littleEndianBytesToSingle(y));
         case '64'
            x = littleEndianBytesToDouble(y);
         otherwise
            error('unknown precision')
      end
   otherwise 
      error('unknown endianess.')
end



function x = bigEndianBytesToSingle(x)
x = typecast(uint8(x),'uint32');
x = typecast(swapbytes(x),'single');

function x = bigEndianBytesToDouble(x)
x = typecast(uint8(x),'uint64');
x = typecast(swapbytes(x),'double');

function x = littleEndianBytesToSingle(x)
x = typecast(uint8(x),'uint32');
x = typecast(x,'single');

function x = littleEndianBytesToDouble(x)
x = typecast(uint8(x),'uint64');
x = typecast(x,'double');
