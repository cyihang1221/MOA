function fprintfln(fid,varargin)
%Magnus Åberg


if ~exist('fid','var')
   fid = 1;
end

if nargin >1
   fprintf(fid,varargin{:});
end

%nl = char([10 13]);
%fprintf(fid,'%2s',nl);
fprintf(fid,'\n');