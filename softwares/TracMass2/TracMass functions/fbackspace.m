function [varargout] = fbackspace(fid,str)
%BACKSPACE Uses fprintf to backspace the length of 'str'
%
% Magnus Åberg, mgna@novonordisk.dk
% 2005-02-15
if nargin==1,
   str = fid;
   fid = 1;
end
tmp_str = '';
if iscell(str)
   for i = 1:length(str)
      tmp_str = [tmp_str, str{i}];
   end
   str = tmp_str;
end
%count = fprintf(fid,repmat('\b',1,length(sprintf(str))));
if numel(str)>0,
   count = fprintf(fid,repmat('\b',1,numel(str)));
end

if nargout == 1,
   varargout{1} = count;
end