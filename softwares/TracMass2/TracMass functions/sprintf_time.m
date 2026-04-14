function str = sprintf_time(seconds,varargin)
%by: Magnus Åberg
sep = '::';
if nargin > 1,
   sep = varargin{1};
end

if ~isfinite(seconds),
   str = num2str(seconds);
   return
end

try
   hrs = floor(seconds/3600);
   mins = floor(mod(seconds,3600)/60);
   secs = floor(mod(seconds,60));
   thsnds = floor(1000*(mod(seconds,1)));

   T = [hrs(:) mins(:) secs(:) thsnds(:)];
   mask = false(4,1);
   fmt = '';
   fmtStart = 0;
   totalLength = 0;
   if any(hrs>0),
      len = floor(log10(max(hrs(:))))+1;
      fmt = [fmt, '%',int2str(len),'i',sep(1)];
      fmtStart = 1;
      mask(1) = true;
      totalLength = totalLength + len+1;
   end
   if fmtStart || any(mins>0)
      fmt = [fmt, '%2i',sep(2)];
      fmtStart = 1;
      mask(2) = true;
      totalLength = totalLength + 3;
   end

   fmt = [fmt,'%2i'];
   fmtStart = 1;
   mask(3) = true;
   totalLength = totalLength + 2;

   if fmtStart && any(thsnds)
      fmt = [fmt, '.%3i'];
      mask(4) = true;
      totalLength = totalLength + 4;
   end
   if length(sep)==3,
      fmt = [fmt,sep(3)];
      totalLength = totalLength + 1;
   end

   str = zeros(length(seconds(:)),totalLength);
   for i = 1:length(seconds(:)),
      str(i,:) = sprintf(fmt,T(i,mask)');
   end

   [spaceR,spaceC] = find(str==' ');
   inds = spaceC>2;
   str(spaceR(inds),spaceC(inds))='0';
   str = char(str);

catch
   disp(lasterr)
   str = '--:--:--';
end