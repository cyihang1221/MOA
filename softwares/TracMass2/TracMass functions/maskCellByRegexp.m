function [tf] = maskCellByRegexp(strs,pat)
%Magnus Åberg
assert(iscell(strs),'maskCellByRegexp: Input is not of class cell.')
dim = size(strs);
N = numel(strs);

result = regexp(strs,pat);

tf = false(dim);
for i = 1:N
   tf(i) = ~isempty(result{i});
end
   
